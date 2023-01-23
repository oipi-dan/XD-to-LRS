import arcpy
from xd_to_rns import move_to_closest_int

inputIntersections = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_intersections'
print('Creating Intersection Layer')
intersectionResults = arcpy.MakeFeatureLayer_management(inputIntersections, "int")
lyrIntersections = intersectionResults.getOutput(0)

print('Finding Nearest Intersection')
geom = arcpy.PointGeometry(arcpy.Point(181130.11460000277,174557.64059999958), arcpy.SpatialReference(3969))

point, moved= move_to_closest_int(geom, lyrIntersections)

print(moved)
print(point)