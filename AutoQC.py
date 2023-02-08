import arcpy
import logging
import pandas as pd

"""
Compare the following to create a confidence score:
    - Total segment length
    - Difference in centroid location
    - Segment bearing (direction from start point to end point)
        - Total Bearing
        - Begin point to mid-point
        - Mid-point to end point
    - Hausdorff distance (measurement of shape similarity)


"""

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG) # Set the debug level here
fileHandler = logging.FileHandler(f'AutoQC.log', mode='w')
log.addHandler(fileHandler)

def hausdorff_distance(geom1, geom2, normalized):
    distances = []
    for part in geom1:
        for point in part:
            point = arcpy.PointGeometry(point, arcpy.SpatialReference(3969))
            distances.append(point.distanceTo(geom2))
    
    # Normalize by reducing each distance by minimum distance.  This will "move" the
    # closest parts of geom1 and geom2 together to better compare geometry shape
    if normalized:
        distances = [dist - min(distances) for dist in distances]

    hausdorff = max(distances)
    return hausdorff


def is_similar_shape(geom1, geom2, normalized=False):
    if not geom1:
        return False, None

    # Get min score from both comparisons
    hausdorff_1 = hausdorff_distance(geom1, geom2, normalized=normalized)
    hausdorff_2 = hausdorff_distance(geom2, geom1, normalized=normalized)

    hausdorff = round(min([hausdorff_1, hausdorff_2]), 2)

    if hausdorff < (geom1.getLength()/10) and hausdorff < 10:
        return True, hausdorff
    else:
        return False, hausdorff


def get_bearing(begin, end):
    return round(begin.angleAndDistanceTo(end, 'PLANAR')[0])


def compare_bearing(XDGeom, geom2, part):
    XDGeom_Begin = arcpy.PointGeometry(XDGeom.firstPoint)
    XDGeom_End = arcpy.PointGeometry(XDGeom.lastPoint)

    # Conflation geom's direction is not preserved after dissolving.  Try to find
    # the correct start point based on distance from XDGeom_Begin

    geom2_firstPoint = arcpy.PointGeometry(geom2.firstPoint)
    geom2_lastPoint = arcpy.PointGeometry(geom2.lastPoint)

    if XDGeom_Begin.distanceTo(geom2_firstPoint) < XDGeom_Begin.distanceTo(geom2_lastPoint):
        geom2_Begin = arcpy.PointGeometry(geom2.firstPoint)
        geom2_End = arcpy.PointGeometry(geom2.lastPoint)
    else:
        geom2_Begin = arcpy.PointGeometry(geom2.lastPoint)
        geom2_End = arcpy.PointGeometry(geom2.firstPoint)



    if part == 'First':
        XDGeom_End = XDGeom.positionAlongLine(0.5, 'TRUE')
        geom2_End = geom2.positionAlongLine(0.5, 'TRUE')
    
    if part == 'Second':
        XDGeom_Begin = XDGeom.positionAlongLine(0.5, 'TRUE')
        geom2_Begin = geom2.positionAlongLine(0.5, 'TRUE')


    XDGeom_Bearing = get_bearing(XDGeom_Begin, XDGeom_End)
    geom2_Bearing = get_bearing(geom2_Begin, geom2_End)

    return abs(XDGeom_Bearing - geom2_Bearing), XDGeom_Bearing, geom2_Bearing


def add_confidence_field(conflationLayer, scores):
    # Add confidence filed to conflation layer
    fields = [field.name for field in arcpy.ListFields(conflationLayer)]
    if 'confidence' not in fields:
        arcpy.AddField_management(conflationLayer, 'confidence', 'SHORT')
    
    # Create dictionary containing scores by XDSegID
    scoreDict = {}
    for score in scores:
        scoreDict[score['XDSegID']] = score['confidence']
    
    # Add scores to conflation layer
    with arcpy.da.UpdateCursor(conflationLayer, ['XDSegID', 'confidence']) as cur:
        for row in cur:
            XDSegID = row[0]
            if XDSegID in scoreDict.keys():
                row[1] = scoreDict[XDSegID]
                cur.updateRow(row)
    


def get_confidence_score(XDSegID, XDGeom, conflationGeom):
    """
    
    inputs:
        XDSegID (int) - The XD Segment ID
        XDGeom (polyline) - The geometry associated with the XD segment
        conflationGeom (polyline) - The dissolved geometry on the LRS from the output conflation
    """

    # Check if input conflation geometry exists
    if not conflationGeom:
        log.debug('    No valid conflation geometry.')
        return 0

    XDLen = round(XDGeom.getLength(), 2)
    conflationLen = round(conflationGeom.getLength(), 2)

    log.debug('    Test Results:')
    ### Tests ###
    # Length
    totalLengthDifference = round(abs(XDLen - conflationLen), 2)
    totalLengthRatio = round(conflationLen / XDLen, 2)
    isSimilarLength = True if 0.75 <= totalLengthRatio <= 1.25 else False
    
    # Shape
    isSimilarShape, hausdorffDistance = is_similar_shape(conflationGeom, XDGeom)
    isSimilarShapeNormalized, hausorffDistanceNormalized = is_similar_shape(conflationGeom, XDGeom, normalized=True)
    
    # Location
    XDCentroid = arcpy.PointGeometry(XDGeom.centroid, arcpy.SpatialReference(3969))
    conflationCentroid = arcpy.PointGeometry(conflationGeom.centroid, arcpy.SpatialReference(3969))
    centroidDifference = round(XDCentroid.distanceTo(conflationCentroid))

    # Bearing
    segmentBearing_Total, XDBearing_Total, ConflationBearing_Total = compare_bearing(XDGeom, ConflationGeom, 'Total')
    segmentBearing_FirstHalf, XDBearing_First, ConflationBearing_First = compare_bearing(XDGeom, ConflationGeom, 'First')
    segmentBearing_SecondHalf, XDBearing_Second, ConflationBearing_Second = compare_bearing(XDGeom, ConflationGeom, 'Second')
    isSimilarBearing = True if segmentBearing_Total + segmentBearing_FirstHalf + segmentBearing_SecondHalf <= 30 else False


    ### Calculate final score: ###
    finalScore = 1 # Starts with perfect score

    subtraction = [
        0 if totalLengthDifference < 100 else 0.1,
        0 if isSimilarLength else 0.3,
        0 if isSimilarShape else 0.3,
        0 if isSimilarShapeNormalized else 0.3,
        0 if centroidDifference < 100 else 0.1,
        0 if isSimilarBearing else 0
    ]
    
    for item in subtraction:
        finalScore -= item

    if finalScore < 0:
        finalScore = 0

    finalScore = round(finalScore * 100)



    log.debug(f'      Length Comparison:')
    log.debug(f'        totalLengthDifference: {totalLengthDifference}m ({XDLen}m [XD] - {conflationLen}m [Conflation])')
    log.debug(f'        totalLengthRatio: {totalLengthRatio}')
    log.debug(f'        isSimilarLength: {isSimilarLength}')

    log.debug(f'\n      Shape Comparison:')
    log.debug(f'        isSimilarShape: {isSimilarShape} (hausdorff distance: {hausdorffDistance}m)')
    log.debug(f'        isSimilarShapeNormalized: {isSimilarShapeNormalized} (normalized hausdorff distance: {hausorffDistanceNormalized}m)')

    log.debug(f'\n      Location Comparison:')
    log.debug(f'        XD Centroid: {XDCentroid.firstPoint.X}, {XDCentroid.firstPoint.Y}')
    log.debug(f'        Conflation Centroid: {conflationCentroid.firstPoint.X}, {conflationCentroid.firstPoint.Y}')    
    log.debug(f'        centroidDifference: {centroidDifference}m')

    log.debug(f'\n      Bearing Comparison:')
    log.debug(f'        segmentBearing_Total: {segmentBearing_Total} (XD: {XDBearing_Total}, Conflation: {ConflationBearing_Total})')
    log.debug(f'        segmentBearing_FirstHalf: {segmentBearing_FirstHalf} (XD: {XDBearing_First}, Conflation: {ConflationBearing_First})')
    log.debug(f'        segmentBearing_SecondHalf: {segmentBearing_SecondHalf} (XD: {XDBearing_Second}, Conflation: {ConflationBearing_Second})')
    log.debug(f'        isSimilarBearing: {isSimilarBearing}')

    log.debug(f'\n      Subtraction List: {subtraction}')
    log.debug(f'  Confidence Score: {finalScore}')

    return finalScore



if __name__ == '__main__':
    inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\USA_Virginia'
    inputConflation = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ArcGIS\Default.gdb\RichmondRegionFlipped'

    conflation = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ArcGIS\Default.gdb\conflation'

    outputCSV = r'Output\RichmondRegionQC.csv'
    arcpy.env.overwriteOutput = True

    # Make dissolved copy of input conflation in memory
    arcpy.Dissolve_management(inputConflation, conflation, 'XDSegID')

    # List XDs in dissolved layer
    XDs = [row[0] for row in arcpy.da.SearchCursor(conflation, 'XDSegID')]



    # Build dictionary of geometries
    print('Building XDGeomDict')
    XDGeomDict = {int(row[0]): row[1] for row in arcpy.da.SearchCursor(inputXD, ['XDSegID','SHAPE@'])}


    
    print('Building ConflationGeomDict')
    ConflationGeomDict = {int(row[0]): row[1] for row in arcpy.da.SearchCursor(conflation, ['XDSegID','SHAPE@'])}
 
    output = []
    for XD in XDs:
        log.debug(f'\n\n=== Processing {XD} ===')

        # Get geometries
        XDGeom = XDGeomDict[XD]
        ConflationGeom = ConflationGeomDict[XD]

        confidence = get_confidence_score(XD, XDGeom, ConflationGeom)

        record = {
            'XDSegID': XD,
            'confidence': confidence
        }

        output.append(record)

    print(f'Saving output CSV to {outputCSV}')    
    df = pd.DataFrame(output)
    df.to_csv(outputCSV, index=False)

    print(f'Adding confidence field to {inputConflation}')
    add_confidence_field(inputConflation, output)