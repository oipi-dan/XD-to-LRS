import arcpy
from collections import Counter
import logging
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) # Set the debug level here
fileHandler = logging.FileHandler(f'XD.log', mode='w')
log.addHandler(fileHandler)

count_firstIteration = 0
count_secondIteration = 0
count_error = 0
error_list = []

class XDSegment:
    def __init__(self, record):
        self.XDSegID = record[0]
        self.RoadNumber = record[1]
        self.RoadName = record[2]
        self.SlipRoad = record[3]
        self.Geom = record[4]

        self.BeginPoint = arcpy.PointGeometry(self.Geom.firstPoint,arcpy.SpatialReference(3969))
        self.EndPoint = arcpy.PointGeometry(self.Geom.lastPoint,arcpy.SpatialReference(3969))
        self.MidPoint = self.Geom.positionAlongLine(0.5, True)


def get_begin_middle_end(geom):
    """ Returns the begin, middle, and end points of the input geometry """

    return


def find_nearby_routes(point, lrs, searchDistance="10 METERS"):
    """ Given an input point, will return a list of all routes within the searchDistance """

    routes = []
    arcpy.management.SelectLayerByLocation(lrs, 'WITHIN_A_DISTANCE', point, searchDistance)
    with arcpy.da.SearchCursor(lrs, 'RTE_NM') as cur:
        for row in cur:
            routes.append(row[0])

    return routes


def get_most_common(c):
    """ Returns a list of the most common values found in the input counter c """
    freq_list = list(c.values())
    max_cnt = max(freq_list)
    total = freq_list.count(max_cnt)
    most_commons = c.most_common(total)
    
    return most_commons


def get_point_mp(inputPointGeometry, lrs, rte_nm, lyrIntersections):
    """ Locates the MP value of an input point along the LRS
        ** The spatial reference of the input must match the spatial reference
           of the lrs! **
    Input:
        inputPointGeometry - an arcpy PointGeometry object
        lrs - a reference to the lrs layer
        rte_nm - the lrs rte_nm that the polyline will be placed on
    Output:
        mp - the m-value of the input point
    """
    try:
        # Get the geometry for the LRS route
        arcpy.management.SelectLayerByAttribute(lrs,'CLEAR_SELECTION')

        with arcpy.da.SearchCursor(lrs, "SHAPE@", "RTE_NM = '{}'".format(rte_nm)) as cur:
            for row in cur:
                RouteGeom = row[0]


        rteMeasure = RouteGeom.measureOnLine(inputPointGeometry)
        rtePosition = RouteGeom.positionAlongLine(rteMeasure)

        rtePosition, moved = move_to_closest_int(rtePosition, lyrIntersections)

        if moved:
            rteMeasure = RouteGeom.measureOnLine(rtePosition)
            rtePosition = RouteGeom.positionAlongLine(rteMeasure)

        mp = rtePosition.firstPoint.M
        return round(mp, 3)
    
    except Exception as e:
        print(e)
        print(rte_nm)
        return None


def get_points_along_line(geom, d=50):
    """ Find points every m distance along the input polyline geometry and
        return them as a list """
    
    segLen = geom.getLength('GEODESIC','METERS')
    log.debug(f'      segLen: {segLen}')

    # For short segments, reduce m to increase the number of test points
    if segLen <= 150:
        d = segLen / 4
        log.debug(f'      Reduced d to {d}')
    points = []

    m = 0
    while m < segLen:
        points.append(geom.positionAlongLine(m))
        m += d

    for point in points:
        log.debug(f'        {point.firstPoint.X}, {point.firstPoint.Y}')
    return points


def move_to_closest_int(geom, lyrIntersections, testDistance=30):
    """ Returns input testGeom moved to the nearest intersection """

    arcpy.SelectLayerByLocation_management(lyrIntersections, "INTERSECT", geom, testDistance)
    intersections = [row[0] for row in arcpy.da.SearchCursor(lyrIntersections, "SHAPE@")]
    if len(intersections) == 0:
        log.debug(f"        No intersections within {testDistance}m distance.  Returning testGeom.")
        moved = False
        return geom, moved
    
    if len(intersections) == 1:
        log.debug(f"        One intersection within {testDistance}m distance.  Returning intersection at {intersections[0].firstPoint.X}, {intersections[0].firstPoint.Y}.")
        moved = True
        return intersections[0].firstPoint, moved

    log.debug(f"        {len(intersections)} intersections found.  Returning closest intersection.")
    closestInt = intersections[0]
    closestIntDist = testDistance
    for intersection in intersections:
        dist = geom.distanceTo(intersection)
        if dist < closestIntDist:
            closestInt = intersection
            closestIntDist = dist
    
    log.debug(f"        Returning intersection at {closestInt.firstPoint.X}, {closestInt.firstPoint.Y}")
    moved = True
    return closestInt.firstPoint, moved


def compare_route_name_similarity(rteA, rteB, lrs):
    """ A frequent problem occurs when both directions of a divided road are identified
        as a match, but only one direction should be used.  This function attempts to
        identify these cases and only return one route if they are very similar.  In these
        cases, the prime direction will take priority.  If the XD segment belongs to the
        non-prime side, this will be fixed in the route flipping step. """
    log.debug(f"Comparing similarity between '{rteA}' and '{rteB}'")
    sm = SequenceMatcher(None, rteA, rteB)
    similarity = sm.ratio()
    log.debug(f'Similarity Ratio: {similarity}')
    if similarity >= 0.9: # Likely the same route
        # Identify the prime direction
        rte_parent_rte_nm = [row[0] for row in arcpy.da.SearchCursor(lrs, 'RTE_PARENT_RTE_NM', f"RTE_NM IN ('{rteA}','{rteB}')") if row[0] is not None]
        print(rte_parent_rte_nm)
        if len(rte_parent_rte_nm) == 1:
            log.debug(f'Returning {rte_parent_rte_nm}')
            return rte_parent_rte_nm
    
    log.debug(f'Returning {[rteA, rteB]}')
    return [rteA, rteB]


def find_common_intersection(rteA, rteB, lrs, intersections):
    """ Given two rte_nms, this will return the intersection objectID if the two
        routes share a single intersection """

    def get_ints(rte_nm, lrs, intersections):
        print(f'get_ints({rte_nm})')
        arcpy.management.SelectLayerByAttribute(lrs,'CLEAR_SELECTION')
        arcpy.management.SelectLayerByAttribute(intersections,'CLEAR_SELECTION')

        geom = [row[0] for row in arcpy.da.SearchCursor(lrs, 'SHAPE@', f"RTE_NM = '{rte_nm}'")][0]

        arcpy.SelectLayerByLocation_management(intersections, 'WITHIN_A_DISTANCE', geom, '10 METERS', 'NEW_SELECTION')


        return list(intersections.getSelectionSet())

    rteAInts = get_ints(rteA, lrs, intersections)
    rteBInts = get_ints(rteB, lrs, intersections)


    commonInts = [rte for rte in rteAInts if rte in rteBInts]
    print('commonInts: ', commonInts)

    if len(commonInts) == 1:
        return commonInts[0]
    
    return None






def first_iteration(XDSeg, lrs):
    """ Find the nearby routes for the begin, middle, and end point of the XD segment.
        If only one route appears, then that is considered the likely match. """

    log.debug('    First Iteration...')
    routes = Counter()
    for point in [XDSeg.BeginPoint, XDSeg.MidPoint, XDSeg.EndPoint]:
        nearbyRoutes = find_nearby_routes(point, lrs)
        for route in nearbyRoutes:
            routes[route] += 1

    if len(routes) == 0:
        log.debug(f'      -- Failed to find matching route --')
        return None

    log.debug(f'      Nearby routes found:\n')
    log.debug(f'      {routes}\n')
    
    # This is different than routes.most_common().  Get_most_common() will return only the 
    # most common value(s) rather than ordering the results by most common.
    mostCommonRoutes = get_most_common(routes) 

    log.debug(f'      Most Common: {mostCommonRoutes}')
    log.debug(f'      Most Common Count: {len(mostCommonRoutes)}')

    # If only one route is found 3 times, return matching rte_nm
    if len(mostCommonRoutes) == 1 and mostCommonRoutes[0][1] == 3:
        log.debug(f'      -- Matching route found --')
        return mostCommonRoutes[0][0]
    else:
        log.debug(f'      -- Failed to find matching route --')
        return None


def second_iteration(XDSeg, lrs, d=25):
    """ Similar to first_iteration, except the nearby routes are found every d
        distance along the line. """

    log.debug('\n    Second Iteration...')
    routes = Counter()
    
    # Get a list of points every d distance along segment
    points = get_points_along_line(XDSeg.Geom, d)

    # Get nearby routes for each point
    for point in points:
        nearbyRoutes = find_nearby_routes(point, lrs)
        for route in nearbyRoutes:
            routes[route] += 1

    log.debug(f'      Nearby routes found:\n')
    log.debug(f'      {routes}\n')
    mostCommonRoutes = routes.most_common()

    log.debug(f'      Most Common: {mostCommonRoutes}')

    # Get matching routes where there are at least 3 matches
    routes = [route[0] for route in mostCommonRoutes if route[1] >= 3]
    log.debug(f'      Most Common Count (>= 3): {len(routes)}')

    if len(routes) >= 1:
        log.debug(f'      -- Matching route(s) found --')
        return routes
    else:
        log.debug(f'      -- Failed to find matching route(s) --')
        return None

    return None


def third_iteration(XDSeg):


    return


def match_xd_to_lrs(xd, lrs, intersections, xdFilter='', lrsFilter=''):
    """ For each xd segment in input xd, attempt to locate on the lrs.  If unable to locate,
        the record will contain null values for all except XDSegID """

    global count_firstIteration
    global count_secondIteration
    global count_error
    global error_list

    output = []
    XDFields = ['XDSegID','RoadNumber','RoadName','SlipRoad','SHAPE@']

    print('Creating LRS layer')
    lrs = arcpy.MakeFeatureLayer_management(lrs, "LRS", lrsFilter)
    lrs = lrs.getOutput(0)

    print('Creating Intersection Layer')
    intersectionResults = arcpy.MakeFeatureLayer_management(intersections, "int")
    lyrIntersections = intersectionResults.getOutput(0)

    # These serve no purpose other than to fix a stuid bug in arcpy that prevents
    # select by attributes and select by location from working on these layers.
    # The only fix I've found is to hit them both with a search cursor first.
    DumbWorkaround_Routes = [row[0] for row in arcpy.da.SearchCursor(lrs,'RTE_NM')]
    DumbWorkaround_Ints = [row[0] for row in arcpy.da.SearchCursor(lyrIntersections, 'INTERSECTI')]

    with arcpy.da.SearchCursor(xd, XDFields, xdFilter) as cur:
        for row in cur:
            XDSeg = XDSegment(row)
            log.debug(f'\n\n  Processing {XDSeg.XDSegID}')

            # Each XD Segment is match tested against the LRS in 3 iterations of increasing complexity.
            # If a single match is found, the next iterations are passed

            #####################
            ## FIRST ITERATION ##
            #####################
            # Find the nearby routes for the begin, middle, and end point of the XD segment.
            # If only one route appears, then that is considered the likely match.
            segResults = first_iteration(XDSeg, lrs)
            if segResults:
                count_firstIteration += 1
                output.append([XDSeg.XDSegID, segResults, get_point_mp(XDSeg.BeginPoint, lrs, segResults, lyrIntersections), get_point_mp(XDSeg.EndPoint, lrs, segResults, lyrIntersections)])

                continue
            
            ######################
            ## SECOND ITERATION ##
            ######################
            # Similar to first_iteration, except the nearby routes are found every d
            # distance along the line.
            segResults = second_iteration(XDSeg, lrs)
            if segResults:
                count_secondIteration += 1

                # If two routes are in results, first make sure that they are acutally two
                # different routes rather than both directions of the same route, then
                # attempt to find a common intersection between the two to
                # ensure that the resulting event table is a single continuous line
                if len(segResults) == 2:
                    log.debug('        Two routes found.  Comparing RTE_NN values for duplicated route...')
                    compareResult = compare_route_name_similarity(segResults[0], segResults[1], lrs)

                    if len(compareResult) == 1: # Both directions of the same route found.  We will only use the prime direction
                        print('\nHA HA HA')
                        print('segResults:',segResults,'compareResult:',compareResult)
                        segResults = compareResult
                        print(segResults)

                    if len(compareResult) != 1: # Two individual routes found.  Continue mapping on two routes
                        log.debug('        Two routes found.  Attempting to find common intersection...')
                        commonInt = find_common_intersection(segResults[0], segResults[1], lrs, lyrIntersections)
                        if commonInt is not None:
                            arcpy.management.SelectLayerByAttribute(lyrIntersections,'CLEAR_SELECTION')
                            commonIntGeom = [row[0] for row in arcpy.da.SearchCursor(lyrIntersections, 'SHAPE@', f'OBJECTID_1 = {commonInt}')][0]
                            log.debug(f'        commonInt: {commonInt}')
                            log.debug(f'        commonIntGeom: {(commonIntGeom.firstPoint.X, commonIntGeom.firstPoint.Y)}')

                            # Of these two routes, determine which is closer to the XD begin point
                            [route1,route1Geom], [route2,route2Geom] = [[row[0],row[1]] for row in arcpy.da.SearchCursor(lrs, ['rte_nm','SHAPE@'], f"RTE_NM in ('{segResults[0]}','{segResults[1]}')")]

                            log.debug(f'              XDSeg.BeginPoint: ({XDSeg.BeginPoint.firstPoint.X},{XDSeg.BeginPoint.firstPoint.Y})')
                            log.debug(f'              {[route1,route1Geom], [route2,route2Geom]}')
                            log.debug(f'              {XDSeg.BeginPoint.distanceTo(route1Geom)}')
                            log.debug(f'              {XDSeg.BeginPoint.distanceTo(route2Geom)}')


                            if XDSeg.BeginPoint.distanceTo(route1Geom) < XDSeg.BeginPoint.distanceTo(route2Geom):
                                firstRoute = route1
                                secondRoute = route2
                            else:
                                firstRoute = route2
                                secondRoute = route1
                            

                            firstSegment = [
                                XDSeg.XDSegID,
                                firstRoute,
                                get_point_mp(XDSeg.BeginPoint, lrs, firstRoute, lyrIntersections),
                                get_point_mp(commonIntGeom, lrs, firstRoute, lyrIntersections)
                            ]
                            
                            secondSegment = [
                                XDSeg.XDSegID,
                                secondRoute,
                                get_point_mp(commonIntGeom, lrs, secondRoute, lyrIntersections),
                                get_point_mp(XDSeg.EndPoint, lrs, secondRoute, lyrIntersections)
                            ]

                            log.debug(f'        firstSegment: {firstRoute}')
                            log.debug(f'          XDSeg.BeginPoint: ({XDSeg.BeginPoint.firstPoint.X},{XDSeg.BeginPoint.firstPoint.Y})')
                            log.debug(f'          commonIntGeom: ({commonIntGeom.firstPoint.X},{commonIntGeom.firstPoint.Y})')

                            log.debug(f'        secondSegment: {secondRoute}')
                            log.debug(f'          commonIntGeom: ({commonIntGeom.firstPoint.X},{commonIntGeom.firstPoint.Y})')
                            log.debug(f'          XDSeg.EndPoint: ({XDSeg.EndPoint.firstPoint.X},{XDSeg.EndPoint.firstPoint.Y})')

                            output.append(firstSegment)
                            output.append(secondSegment)
                            
                            continue

                for route in segResults:
                    output.append([XDSeg.XDSegID, route, get_point_mp(XDSeg.BeginPoint, lrs, route, lyrIntersections), get_point_mp(XDSeg.EndPoint, lrs, route, lyrIntersections)])
                
                continue

            segResults = third_iteration(XDSeg)
            if segResults:
                output.append(segResults)
                continue

            
            count_error += 1
            error_list.append(XDSeg.XDSegID)
            output.append([XDSeg.XDSegID, None, None, None])
            
    
    return output


if __name__ == '__main__':
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\RichmondSample.shp'
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\RichmondXD'
    inputLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'
    inputIntersections = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_intersections'
    start = datetime.now()

    # Test set of XD Segments
    testList = [132436349, 441050854, 132464894]
    testList = [134703088,
        429100710,
        441066134,
        441066135,
        1310507812]
    testListStr = ''
    testSQL = ''
    if len(testList) > 0:
        for testSeg in testList:
            testListStr += f"'{testSeg}',"
        testSQL = f'XDSegID IN ({testListStr[:-1]})'

    testResults = match_xd_to_lrs(inputXD, inputLRS, inputIntersections, testSQL)
    log.debug(testResults)

    df = pd.DataFrame(testResults, columns=['XDSegID','RTE_NM','BEGIN_MSR','END_MSR'])
    print(df)
    df.to_csv('output.csv', index=False)

    end = datetime.now()
    log.debug(f'\n\nRun Time: {end - start}')
    count_total = sum([count_firstIteration, count_secondIteration, count_error])
    log.debug(f'  Processed {count_total} XD Segments')
    log.debug(f'    First Iteration: {count_firstIteration}, {round(count_firstIteration/count_total*100)}%')
    log.debug(f'    Second Iteration: {count_secondIteration}, {round(count_secondIteration/count_total*100)}%')
    log.debug(f'    Third Iteration: N/A, 0%')
    log.debug(f'    Error: {count_error}, {round(count_error/count_total*100)}%')
    log.debug('      Error list:')
    for segment in error_list:
        log.debug(f'        {segment}')