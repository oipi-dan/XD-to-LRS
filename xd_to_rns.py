import arcpy
from collections import Counter
import logging
import pandas as pd
from datetime import datetime
from difflib import SequenceMatcher
import traceback

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) # Set the debug level here
fileHandler = logging.FileHandler(f'XD.log', mode='w')
log.addHandler(fileHandler)

count_firstIteration = 0
count_secondIteration = 0
count_error = 0
error_list = []

# This is a list of routes where the MP is backwards than expected
# It should be used to correct invalid results and updated with
# new versions LRS if they are corrected
LRS_RTE_ERRORS__REVERSED_MP = [
    'R-VA000SC06624NB'
]

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


class MatchedRoute:
    def __init__(self, rte_nm, XDSeg, lrs):
        self.rte_nm = rte_nm
        self.geom = self.get_geom(lrs)
        self.distanceFromXDSeg = self.get_distance_from_XD_Seg(XDSeg.BeginPoint)
        self.beginPoint = arcpy.PointGeometry(arcpy.Point(0,0))
        self.endPoint = arcpy.PointGeometry(arcpy.Point(0,0))
        self.intersections = None
        self.distanceToClosestIntersection = None


    def get_geom(self, lrs):
        try:
            arcpy.management.SelectLayerByAttribute(lrs,'CLEAR_SELECTION')
            geom = [row[0] for row in arcpy.da.SearchCursor(lrs, 'SHAPE@', f"RTE_NM = '{self.rte_nm}'")][0]
            return geom
        except:
            return None


    def get_distance_from_XD_Seg(self, XDBeginPoint):
        try:
            return XDBeginPoint.distanceTo(self.geom)
        except:
            return None

    
    def get_distance_to_closest_intersection(self, lyrIntersections, XDSeg):
        BeginPoint = XDSeg.BeginPoint
        arcpy.management.SelectLayerByAttribute(lyrIntersections,'CLEAR_SELECTION')
        arcpy.SelectLayerByLocation_management(lyrIntersections, 'WITHIN_A_DISTANCE', self.geom, '5 METERS', 'NEW_SELECTION')
        intersections = [row[0] for row in arcpy.da.SearchCursor(lyrIntersections, 'SHAPE@')]
        for intersection in intersections:
            dist = BeginPoint.distanceTo(intersection)
            if self.distanceToClosestIntersection is None:
                self.distanceToClosestIntersection = dist

            if dist < self.distanceToClosestIntersection:
                self.distanceToClosestIntersection = dist


    
    def __repr__(self):
        return f"'<MatchedRoute {self.rte_nm}': {round(self.distanceFromXDSeg, 3)}m, BeginPoint: {self.beginPoint.firstPoint.X},{self.beginPoint.firstPoint.Y}   EndPoint: {self.endPoint.firstPoint.X},{self.beginPoint.firstPoint.Y}    dist: {self.distanceToClosestIntersection}>"


def get_begin_middle_end(geom):
    """ Returns the begin, middle, and end points of the input geometry """

    return


def find_nearby_routes(point, lrs, searchDistance="9 METERS", rerun=False):
    """ Given an input point, will return a list of all routes within the searchDistance """
    if rerun == True:
        searchDistance = "20 METERS"

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

        # Check for route multipart geometry.  If multipart, find closest part to
        # ensure that the correct MP is returned
        if RouteGeom.isMultipart:
            # Get list of parts
            parts = [arcpy.Polyline(RouteGeom[i], has_m=True) for i in range(RouteGeom.partCount)]

            # Get distances from inputPolyline's mid-point to each route part
            partDists = {inputPointGeometry.distanceTo(part):part for part in parts}

            # Replace RouteGeom with closest polyline part
            RouteGeom = partDists[min(partDists)]


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


def get_points_along_line(geom, d=50, rerun=False):
    """ Find points every d distance along the input polyline geometry and
        return them as a list """
    
    segLen = geom.getLength('GEODESIC','METERS')
    log.debug(f'      segLen: {segLen}')

    # For short segments, reduce m to increase the number of test points
    if segLen <= 150:
        if rerun == False:
            d = segLen / 4
            log.debug(f'      Reduced d to {d}')
        else:            
            d = segLen / 5
            log.debug(f'      Reduced d to {d}')
    points = []

    m = 0
    while m <= segLen:
        points.append(geom.positionAlongLine(m))
        m += d

    for point in points:
        log.debug(f'        {point.firstPoint.X}, {point.firstPoint.Y}')
    
    return points


def move_to_closest_int(geom, lyrIntersections, testDistance=10):
    """ Returns input testGeom moved to the nearest intersection """
    log.debug(f"        move_to_closest_int input geom: {geom.firstPoint.X}, {geom.firstPoint.Y}")

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
    log.debug(f"\n        Comparing similarity between '{rteA}' and '{rteB}'")

    # First check route type (eg, IS, US, etc).  If they do not match, then the routes are different
    rteA_type = rteA[7:9]
    rteB_type = rteB[7:9]
    
    if rteA_type != rteB_type and rteA.startswith('R-VA'):
        log.debug(f"\n        Routes of different type - returning both '{rteA}' and '{rteB}'")
        return [rteA, rteB]

    sm = SequenceMatcher(None, rteA, rteB)
    similarity = sm.ratio()
    log.debug(f'        Similarity Ratio: {similarity}')
    if similarity >= 0.9: # Likely the same route
        # Identify the prime direction
        rte_parent_rte_nm = [row[0] for row in arcpy.da.SearchCursor(lrs, 'RTE_PARENT_RTE_NM', f"RTE_NM IN ('{rteA}','{rteB}')") if row[0] is not None]

        if len(rte_parent_rte_nm) == 1:
            log.debug(f'        Returning {rte_parent_rte_nm}\n')
            return rte_parent_rte_nm
    
    log.debug(f'        Returning {[rteA, rteB]}\n')
    return [rteA, rteB]


def find_common_intersection(rteA, rteB, lrs, intersections, XDSeg, commonIntsUsed=[]):
    """ Given two rte_nms, this will return the intersection objectID if the two
        routes share a single intersection """

    def get_ints(rte_nm, lrs, intersections):
        arcpy.management.SelectLayerByAttribute(lrs,'CLEAR_SELECTION')
        arcpy.management.SelectLayerByAttribute(intersections,'CLEAR_SELECTION')

        geom = [row[0] for row in arcpy.da.SearchCursor(lrs, 'SHAPE@', f"RTE_NM = '{rte_nm}'")][0]

        arcpy.SelectLayerByLocation_management(intersections, 'WITHIN_A_DISTANCE', geom, '5 METERS', 'NEW_SELECTION')


        return list(intersections.getSelectionSet())

    rteAInts = get_ints(rteA, lrs, intersections)
    rteBInts = get_ints(rteB, lrs, intersections)

    commonInts = [rte for rte in rteAInts if rte in rteBInts]

     # Remove int as an option if it's already been used
    if len(commonIntsUsed) != 0:
        commonInts = [int for int in commonInts if int not in commonIntsUsed]

    if len(commonInts) == 1:
        log.debug(f'        One common intersection found: {commonInts}\n')
        return commonInts[0]

    if len(commonInts) > 1:
        log.debug(f'        {len(commonInts)} common intersections found: {commonInts}\n')
        # Attempt to narrow down intersections to one
        log.debug(f'        Selecting only nearby common intersections')
        arcpy.management.SelectLayerByAttribute(intersections,'CLEAR_SELECTION')
        arcpy.SelectLayerByLocation_management(intersections, "INTERSECT", XDSeg.Geom, "10 METERS")
        nearbyInts = intersections.getSelectionSet()
        commonInts2 = [int for int in nearbyInts if int in commonInts]
        if len(commonInts2) == 1:
            log.debug(f'        {len(commonInts2)} nearby common intersection found.  Returning {commonInts2[0]}')
            return commonInts2[0]

        log.debug(f'        {len(commonInts2)} nearby common intersections found.  Returning int closest to end point and hoping for the best')
        closestInt = commonInts[0]
        closestIntDist = None
        for intersection in commonInts:
            intGeom = [row[0] for row in arcpy.da.SearchCursor(intersections,'SHAPE@',f'ObjectID_1 = {intersection}')][0]
            dist = XDSeg.EndPoint.distanceTo(intGeom)
            if closestIntDist is None:
                closestIntDist = dist
                continue

            if dist < closestIntDist:
                closestInt = intersection
                closestIntDist = dist

        return closestInt


    log.debug('        No common intersections found\n')
    return None


def is_similar_shape(geom1, rte_nm, lrs):
    arcpy.management.SelectLayerByAttribute(lrs,'CLEAR_SELECTION')
    geom2 = [row[0] for row in arcpy.da.SearchCursor(lrs, 'SHAPE@', f"RTE_NM = '{rte_nm}'")][0]
    rawDistances = []
    finalDistances = []

    # Compare geom1 to geom2
    for part in geom1:
        for point in part:
            point = arcpy.PointGeometry(point, arcpy.SpatialReference(3969))
            rawDistances.append(point.distanceTo(geom2))
    
    # Normalize by reducing each distance by minimum distance.  This will "move" the
    # closest parts of geom1 and geom2 together to better compare geometry shape
    rawDistances = [dist - min(rawDistances) for dist in rawDistances]

    maxDist = max(rawDistances)
    finalDistances.append(maxDist)

    # Compare geom2 to geom1
    rawDistances = []
    geom2 = geom1.buffer(20).intersect(geom2,2)
    for part in geom2:
        for point in part:
            point = arcpy.PointGeometry(point, arcpy.SpatialReference(3969))
            rawDistances.append(point.distanceTo(geom1))
    
    # Normalize by reducing each distance by minimum distance.  This will "move" the
    # closest parts of geom1 and geom2 together to better compare geometry shape
    rawDistances = [dist - min(rawDistances) for dist in rawDistances]

    maxDist = max(rawDistances)
    finalDistances.append(maxDist)

    # Get min score from both comparisons
    hausdorff = min(finalDistances)

    if hausdorff < (geom1.getLength()/4):
        return True
    else:
        return False



def first_iteration(XDSeg, lrs, rerun=False):
    """ Find the nearby routes for the begin, middle, and end point of the XD segment.
        If only one route appears, then that is considered the likely match. """

    log.debug('    First Iteration...')
    routes = Counter()
    for point in [XDSeg.BeginPoint, XDSeg.MidPoint, XDSeg.EndPoint]:
        nearbyRoutes = find_nearby_routes(point, lrs, rerun=rerun)
        for route in nearbyRoutes:
            routes[route] += 1

    if len(routes) == 0:
        if rerun == False:
        # Try again with longer distance before trying more detailed approach
            log.debug(f'\n\n      Failed to find matching route - trying larger search distance')
            results = first_iteration(XDSeg, lrs, rerun=True)
            if results:
                return results
            else:
                log.debug(f'      -- Failed to find matching route --')
                return None

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
        if rerun == False:
        # Try again with longer distance before trying more detailed approach
            log.debug(f'\n\n      Failed to find matching route - trying larger search distance')
            results = first_iteration(XDSeg, lrs, rerun=True)
            if results:
                # Test Hausdorff Distance to ensure random route wasn't picked up
                if is_similar_shape(XDSeg.Geom, results, lrs):
                    return results
                else:
                    log.debug(f'      -- Shape not similar enough: Failed to find matching route --')
                    return None
            else:
                log.debug(f'      -- Failed to find matching route --')
                return None
        log.debug(f'      -- Failed to find matching route --')
        return None


def second_iteration(XDSeg, lrs, d=25, rerun=False):
    """ Similar to first_iteration, except the nearby routes are found every d
        distance along the line. """

    if rerun == False:
        log.debug('\n    Second Iteration...')
    else:
        log.debug('\n    Third Iteration...')

    routes = Counter()
    
    # Get a list of points every d distance along segment
    points = get_points_along_line(XDSeg.Geom, d, rerun=rerun)

    # Get nearby routes for each point
    for point in points:
        nearbyRoutes = find_nearby_routes(point, lrs)
        for route in nearbyRoutes:
            routes[route] += 1

    log.debug(f'\n      Nearby routes found:')
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
        if rerun == False:
            # Try reducing the distance farther
            log.debug(f'      Reducing d to 10...\n')
            routes = second_iteration(XDSeg, lrs, d=10, rerun=True)
            if routes is not None:
                return routes
            else:
                log.debug(f'      -- Failed to find matching route(s) --')
                return None

    log.debug(f'      -- Failed to find matching route(s) --')
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

    def add_to_output(eventDict, SlipRoad):
        log.debug(f'\nAdding Event: {eventDict}')
        XDSegID = eventDict['XDSegID']
        RTE_NM = eventDict['RTE_NM']
        BEGIN_MSR = eventDict['BEGIN_MSR']
        END_MSR = eventDict['END_MSR']

        # Ramps with non-ramp routes that are digitized in reverse are likely errors and should not be added to output
        if SlipRoad in ('1', 1) and RTE_NM is not None:
            if 'RMP' not in RTE_NM and ((RTE_NM[14:16] in ('NB','EB') and BEGIN_MSR > END_MSR) or (RTE_NM[14:16] in ('SB','WB') and BEGIN_MSR < END_MSR)) and RTE_NM not in LRS_RTE_ERRORS__REVERSED_MP:
                log.debug(f"'{RTE_NM}' is digitized in reverse on a sliproad.  ({BEGIN_MSR} - {END_MSR})Ignoring this event.")
                return

        output.append([XDSegID, RTE_NM, BEGIN_MSR, END_MSR])


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
                event = {
                    "XDSegID": XDSeg.XDSegID,
                    "RTE_NM": segResults,
                    "BEGIN_MSR": get_point_mp(XDSeg.BeginPoint, lrs, segResults, lyrIntersections),
                    "END_MSR": get_point_mp(XDSeg.EndPoint, lrs, segResults, lyrIntersections)
                }

                add_to_output(event, XDSeg.SlipRoad)
                continue
            
            ######################
            ## SECOND ITERATION ##
            ######################
            # Similar to first_iteration, except the nearby routes are found every d
            # distance along the line.
            segResults = second_iteration(XDSeg, lrs)
            if segResults:

                # If only one result, do hausdorff check to ensure it's not picking up a random route
                if len(segResults) == 1 and not is_similar_shape(XDSeg.Geom, segResults[0], lrs):
                    log.debug('        Not a similar shape.  Returning None')
                    event = {
                        "XDSegID": XDSeg.XDSegID,
                        "RTE_NM": None,
                        "BEGIN_MSR": None,
                        "END_MSR": None
                    }
                    count_error += 1
                    error_list.append(XDSeg.XDSegID)
                    add_to_output(event, XDSeg.SlipRoad)
                    
                    continue


                count_secondIteration += 1

                # If two routes are in results, first make sure that they are acutally two
                # different routes rather than both directions of the same route, then
                # attempt to find a common intersection between the two to
                # ensure that the resulting event table is a single continuous line
                if len(segResults) == 2:
                    log.debug('        Two routes found.  Comparing RTE_NN values for duplicated route...')
                    compareResult = compare_route_name_similarity(segResults[0], segResults[1], lrs)

                    if len(compareResult) == 1: # Both directions of the same route found.  We will only use the prime direction
                                                # Continue as if only one result in segResults
                        segResults = compareResult

                    if len(compareResult) != 1: # Two individual routes found.  Continue mapping on two routes
                        log.debug('        Two routes found.  Attempting to find common intersection...')
                        commonInt = find_common_intersection(segResults[0], segResults[1], lrs, lyrIntersections, XDSeg)
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
                            

                            firstSegment = {
                                "XDSegID": XDSeg.XDSegID,
                                "RTE_NM": firstRoute,
                                "BEGIN_MSR": get_point_mp(XDSeg.BeginPoint, lrs, firstRoute, lyrIntersections),
                                "END_MSR": get_point_mp(commonIntGeom, lrs, firstRoute, lyrIntersections)
                            }
                            
                            secondSegment = {
                                "XDSegID": XDSeg.XDSegID,
                                "RTE_NM": secondRoute,
                                "BEGIN_MSR": get_point_mp(commonIntGeom, lrs, secondRoute, lyrIntersections),
                                "END_MSR": get_point_mp(XDSeg.EndPoint, lrs, secondRoute, lyrIntersections)
                            }

                            log.debug(f'        firstSegment: {firstRoute}')
                            log.debug(f'          {firstSegment}')
                            log.debug(f'          XDSeg.BeginPoint: ({XDSeg.BeginPoint.firstPoint.X},{XDSeg.BeginPoint.firstPoint.Y})')
                            log.debug(f'          commonIntGeom: ({commonIntGeom.firstPoint.X},{commonIntGeom.firstPoint.Y})')

                            log.debug(f'        secondSegment: {secondRoute}')
                            log.debug(f'          {secondSegment}')
                            log.debug(f'          commonIntGeom: ({commonIntGeom.firstPoint.X},{commonIntGeom.firstPoint.Y})')
                            log.debug(f'          XDSeg.EndPoint: ({XDSeg.EndPoint.firstPoint.X},{XDSeg.EndPoint.firstPoint.Y})')

                            add_to_output(firstSegment, XDSeg.SlipRoad)
                            add_to_output(secondSegment, XDSeg.SlipRoad)
                            
                            continue
                        
                        if commonInt is None: # Two different routes that do not share an intersection.  Try to use the route that matches most of the two
                            log.debug('        No common routes.  Taking the first (most common) and hoping for the best')
                            event = {
                                "XDSegID": XDSeg.XDSegID,
                                "RTE_NM": segResults[0],
                                "BEGIN_MSR": get_point_mp(XDSeg.BeginPoint, lrs, segResults[0], lyrIntersections),
                                "END_MSR": get_point_mp(XDSeg.EndPoint, lrs, segResults[0], lyrIntersections)
                            }

                            add_to_output(event, XDSeg.SlipRoad)
                            continue

                if len(segResults) > 2:
                    # For each route in segResults, attempt to find the order that they fall by distance from the
                    # begin point of the XDSegment, then map to LRS.
                    try:
                        log.debug('\n        More than two routes found.  Attempting to order results for better mapping.\n')
                        matchedRoutes = []
                        for route in segResults:
                            matchedRoute = MatchedRoute(route, XDSeg, lrs)
                            matchedRoutes.append(matchedRoute)

                        log.debug(f'          {matchedRoute}')
                        # Sort matched routes
                        log.debug(f'          Sorted by distance from begin point:')
                        matchedRoutes = sorted(matchedRoutes, key=lambda x: x.distanceFromXDSeg)
                        log.debug(f'          {matchedRoutes}')

                        # Verify that sorted routes share intersections
                        log.debug(f'\n          Verifying sorting...')
                        SortingVerified = False
                        try:
                            for i, route in enumerate(matchedRoutes):
                                if i < len(matchedRoutes)-1: # Not last route in list
                                    nextRoute = matchedRoutes[i+1]
                                    if find_common_intersection(route.rte_nm, nextRoute.rte_nm,lrs,lyrIntersections,XDSeg) is None:
                                        # Existing order is not correct
                                        log.debug(f'            ...Sorting does not seem to be accurate')

                                        # Attempt to create new order
                                        ### Make this its own function ###
                                        matchedRoutes[0].distanceToClosestIntersection = 0
                                        for route in matchedRoutes[1:]:
                                            route.get_distance_to_closest_intersection(lyrIntersections, XDSeg)
                                        
                                        matchedRoutes = sorted(matchedRoutes, key=lambda x: x.distanceToClosestIntersection)
                                        log.debug(f'              {matchedRoutes}')
                                        



                                        break
                                if i == len(matchedRoutes):
                                    # Sorting seems to be accurate
                                    log.debug(f'            ...Sorting verified')
                                    SortingVerified = True
                        except Exception as e:
                            print(XDSeg.XDSegID, e)
                            log.debug('            Sorting Verification Failed')


                        # Find the begin and end points for each route
                        commonIntsUsed = [] # As intersectinos are used as a common intersection, they will be added here so they won't be used again later.  This is useful for routes that loop back
                        for i, route in enumerate(matchedRoutes):
                            pointsFound = False
                            while pointsFound == False:
                                log.debug(f'\n        Attempting to find begin and end points for {route}')
                                # Find begin point
                                if i == 0: # If first point in matchedRoutes
                                    matchedRoutes[i].beginPoint = XDSeg.BeginPoint
                                else:
                                    matchedRoutes[i].beginPoint = matchedRoutes[i-1].endPoint
                                    log.debug(f'          BeginPoint: {(matchedRoutes[i].beginPoint.firstPoint.X, matchedRoutes[i].beginPoint.firstPoint.Y)}')

                                if route.rte_nm != matchedRoutes[-1].rte_nm: # If a middle route in matchedRoutes
                                    try:
                                        nextRoute_nm = matchedRoutes[i+1].rte_nm
                                        nextRoute_nmGeom = matchedRoutes[i+1].geom
                                    except IndexError: # No more routes to check - the last route in the list has been eliminated
                                        matchedRoutes[i].endPoint = XDSeg.EndPoint
                                        pointsFound = True
                                        break
                                    
                                    # Find closest distance between this route and next route.  If greater than 1m, remove next route
                                    # from potential matches and continue
                                    distanceToNextRoute_nm = route.geom.distanceTo(nextRoute_nmGeom)
                                    log.debug(f'          Distance to next rte_nm: {distanceToNextRoute_nm}')
                                    if distanceToNextRoute_nm > 1:
                                        log.debug(f"          '{nextRoute_nm}' does not appear to intersect '{route.rte_nm}'.")
                                        log.debug(f"            Removing '{nextRoute_nm}'.")
                                        matchedRoutes.pop(i+1)
                                        continue
                                    
                                    log.debug(f"          Attempting to find common int between '{route.rte_nm}' and '{nextRoute_nm}'.")

                                    # Find common intersection between this route and next route
                                    commonInt = find_common_intersection(route.rte_nm, nextRoute_nm, lrs, lyrIntersections, XDSeg, commonIntsUsed)
                                    commonIntsUsed.append(commonInt)

                                    if commonInt is None:
                                        raise Exception("No intersection found")

                                    arcpy.management.SelectLayerByAttribute(lyrIntersections,'CLEAR_SELECTION')
                                    commonIntGeom = [row[0] for row in arcpy.da.SearchCursor(lyrIntersections, 'SHAPE@', f'OBJECTID_1 = {commonInt}')][0]

                                    log.debug(f'          commonInt: {commonInt}')
                                    log.debug(f'          commonIntGeom: {(commonIntGeom.firstPoint.X, commonIntGeom.firstPoint.Y)}')
                                    matchedRoutes[i].endPoint = commonIntGeom
                                    pointsFound = True
                                else: # Last route in matchedRoutes
                                    matchedRoutes[i].endPoint = XDSeg.EndPoint
                                    pointsFound = True
                            
                                                
                        # Add events to output
                        for route in matchedRoutes:
                            event = {
                                "XDSegID": XDSeg.XDSegID,
                                "RTE_NM": route.rte_nm,
                                "BEGIN_MSR": get_point_mp(route.beginPoint, lrs, route.rte_nm, lyrIntersections),
                                "END_MSR": get_point_mp(route.endPoint, lrs, route.rte_nm, lyrIntersections)
                            }
                            
                            add_to_output(event, XDSeg.SlipRoad)
                        continue

                    except Exception as e:
                        print(e)
                        print(traceback.format_exc())
                        log.debug('        Route ordering failed - mapping on LRS without ordering')
                
                for route in segResults:
                    event = {
                            "XDSegID": XDSeg.XDSegID,
                            "RTE_NM": route,
                            "BEGIN_MSR": get_point_mp(XDSeg.BeginPoint, lrs, route, lyrIntersections),
                            "END_MSR": get_point_mp(XDSeg.EndPoint, lrs, route, lyrIntersections)
                        }
                    
                    add_to_output(event, XDSeg.SlipRoad)
                continue

            segResults = third_iteration(XDSeg)
            if segResults:
                output.append(segResults)
                continue

            
            count_error += 1
            error_list.append(XDSeg.XDSegID)
            event = {
                    "XDSegID": XDSeg.XDSegID,
                    "RTE_NM": None,
                    "BEGIN_MSR": None,
                    "END_MSR": None
                }
            
            add_to_output(event, XDSeg.SlipRoad)
    
    return output


if __name__ == '__main__':
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\USA_Virginia'
    inputLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'
    inputIntersections = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_intersections'

    outputCSV = 'RichmondRegion.csv'

    start = datetime.now()

    # Test set of XD Segments
    testList = [132436349, 441050854, 132464894]

    # Error ramps from the ScaryRamp run on 1/26/2023:
    testList = [134738324, 134996374, 135535995, 388662905, 388698981, 388713347, 388778701, 429096136, 429096137, 429096167, 429096171, 429096185, 429103295, 449101341, 450241926, 450263839, 463896182, 1310252276, 1310286249, 1310347687, 1310347925, 1310430701, 1310432326, 1310472698, 1310574212, 1310610077, 1310614847]
    testList = [1310446091]

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
    df.to_csv(outputCSV, index=False)

    end = datetime.now()
    log.info(f'\n\nRun Time: {end - start}')
    count_total = sum([count_firstIteration, count_secondIteration, count_error])
    log.info(f'  Processed {count_total} XD Segments')
    log.info(f'    First Iteration: {count_firstIteration}, {round(count_firstIteration/count_total*100)}%')
    log.info(f'    Second Iteration: {count_secondIteration}, {round(count_secondIteration/count_total*100)}%')
    log.info(f'    Third Iteration: N/A, 0%')
    log.info(f'    Error: {count_error}, {round(count_error/count_total*100)}%')
    log.info('      Error list:')
    for segment in error_list:
        log.info(f'        {segment}')