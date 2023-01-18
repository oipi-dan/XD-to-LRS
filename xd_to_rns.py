import arcpy
from collections import Counter
import logging
import pandas as pd
from datetime import datetime

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) # Set the debug level here
fileHandler = logging.FileHandler(f'XD.log', mode='w')
log.addHandler(fileHandler)


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


def get_point_mp(inputPointGeometry, lrs, rte_nm):
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
        mp = rtePosition.firstPoint.M
        return round(mp, 3)
    
    except Exception as e:
        print(e)
        print(rte_nm)
        return None


def get_points_along_line(geom, m=50):
    """ Find points every m distance along the input polyline geometry and
        return them as a list """
    
    segLen = geom.getLength('GEODESIC','METERS')
    points = []

    m = 0
    while m < segLen:
        points.append(geom.positionAlongLine(m))
        m += 50

    return points


def first_iteration(XDSeg, lrs):
    """ Find the nearby routes for the begin, middle, and end point of the XD segment.
        If only one rout appears, then that is considered the likely match. """

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


def second_iteration(XDSeg, lrs, m=50):
    """ Similar to first_iteration, except the nearby routes are found every m
        distance along the line. """

    log.debug('\n    Second Iteration...')
    routes = Counter()

    # Get a list of points every m distance along segment
    points = get_points_along_line(XDSeg.Geom, m)

    # Get nearby routes for each point
    for point in points:
        nearbyRoutes = find_nearby_routes(point, lrs)
        for route in nearbyRoutes:
            routes[route] += 1

    log.debug(f'      Nearby routes found:\n')
    log.debug(f'      {routes}\n')
    mostCommonRoutes = get_most_common(routes)

    log.debug(f'      Most Common: {mostCommonRoutes}')
    log.debug(f'      Most Common Count: {len(mostCommonRoutes)}')

    if len(mostCommonRoutes) == 1:
        log.debug(f'      -- Matching route found --')
        return mostCommonRoutes[0][0]
    else:
        log.debug(f'      -- Failed to find matching route --')
        return None

    return None


def third_iteration(XDSeg):


    return


def match_xd_to_lrs(xd, lrs, xdFilter='', lrsFilter=''):
    """ For each xd segment in input xd, attempt to locate on the lrs.  If unable to locate,
        the record will contain null values for all except XDSegID """

    output = []
    XDFields = ['XDSegID','RoadNumber','RoadName','SlipRoad','SHAPE@']

    print('Creating LRS layer')
    lrs = arcpy.MakeFeatureLayer_management(lrs, "LRS", lrsFilter)
    lrs = lrs.getOutput(0)


    with arcpy.da.SearchCursor(xd, XDFields, xdFilter) as cur:
        for row in cur:
            XDSeg = XDSegment(row)
            log.debug(f'\n\n  Processing {XDSeg.XDSegID}')

            # Each XD Segment is match tested against the LRS in 3 iterations of increasing complexity.
            # If a single match is found, the next iterations are passed
            segResults = first_iteration(XDSeg, lrs)
            if segResults:
                output.append([XDSeg.XDSegID, segResults, get_point_mp(XDSeg.BeginPoint, lrs, segResults), get_point_mp(XDSeg.EndPoint, lrs, segResults)])
                continue
            
            segResults = second_iteration(XDSeg, lrs)
            if segResults:
                output.append([XDSeg.XDSegID, segResults, get_point_mp(XDSeg.BeginPoint, lrs, segResults), get_point_mp(XDSeg.EndPoint, lrs, segResults)])
                continue

            segResults = third_iteration(XDSeg)
            if segResults:
                output.append(segResults)
                continue

            output.append([XDSeg.XDSegID, None, None, None])
            
    
    return output


if __name__ == '__main__':
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\RichmondSample.shp'
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\RichmondXD'
    inputLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'
    start = datetime.now()

    # Test set of XD Segments
    testList = [132436349, 441050854, 132464894]
    testList = [134687950, 1310292016, 1310240068]
    testListStr = ''
    testSQL = ''
    if len(testList) > 0:
        for testSeg in testList:
            testListStr += f"'{testSeg}',"
        testSQL = f'XDSegID IN ({testListStr[:-1]})'

    testResults = match_xd_to_lrs(inputXD, inputLRS, testSQL)
    log.debug(testResults)

    df = pd.DataFrame(testResults, columns=['XDSegID','RTE_NM','BEGIN_MSR','END_MSR'])
    print(df)
    df.to_csv('output.csv', index=False)

    end = datetime.now()
    log.debug(f'\n\nRun Time: {end - start}')
    

            

    # for XD in XDs:

        # First_Iteration - First we find the nearby routes for the begin, middle, and end point of the XD segment.
            #beginPoint, midPoint, endPoint = get_begin_middle_end(geom)