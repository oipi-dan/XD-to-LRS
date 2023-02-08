import arcpy
import json

MasterLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'

sqlTest = None # To limit the routes to test
sqlGeomDict = None # To limit the LRS geometries to test against
outputJSON = 'LRS_RTE_ERRORS__REVERSED_MP.json'

geomDict = {row[0]: row[1] for row in arcpy.da.SearchCursor(MasterLRS, ['RTE_NM', 'SHAPE@'], sqlGeomDict)}

ReversedRoutes = []


with arcpy.da.SearchCursor(MasterLRS, ['RTE_NM', 'RTE_OPPOSITE_DIRECTION_RTE_NM', 'SHAPE@'], sqlTest) as cur:
    for rte_nm, parent_rte_nm, geom in cur:
        if rte_nm.startswith('S-VA') and rte_nm[7:9] == 'NP':
        # if rte_nm.startswith('R-VA') and rte_nm[14:16] in ['SB', 'WB'] and 'RMP' not in rte_nm:
            try:
                for i in range(geom.partCount):
                # For each segment of route:
                    partGeom = geom.getPart(i)
                    masterGeom = geomDict[parent_rte_nm]
                    
                    # Find the point on the parent route closest to the midpoint of this route segment
                    partMidPoint =  partGeom[round(len(partGeom) / 2)]
                    masterRteMeasure = masterGeom.measureOnLine(partMidPoint)
                    masterRtePoint = masterGeom.positionAlongLine(masterRteMeasure)

                    # Find which side of the route the masterRtePoint is located on
                    queryPointAndDistance = geom.queryPointAndDistance(masterRtePoint)
                    distance = queryPointAndDistance[-2]
                    if distance < 1:
                        continue

                    sideOfRoute = queryPointAndDistance[-1]
                    
                    # If sideOfRoute == True, this means that the master route is located to the right of
                    # the NP route geometry.  Since NP routes should be digitized against the direction
                    # of travel, the PR route geometry should be to the right.  Therefore if
                    # sideOfRoute == False, the S-route is digitized backwards.
                    if not sideOfRoute:
                        ReversedRoutes.append(rte_nm)

                        # Verify if the parent_rte_nm is also reversed
                        masterSideOfRoute = masterGeom.queryPointAndDistance(partMidPoint)[-1]

                        # If masterSideOfRoute == True, then the NP route is to the right of the PR route
                        # and this side is also digitized in reverse.
                        if masterSideOfRoute == True:
                            ReversedRoutes.append(parent_rte_nm)

            except Exception as e:
                print(f'Error on {rte_nm}: {e}')
                

# Save list of reversed routes
with open(outputJSON,'w') as file:
    json.dump(ReversedRoutes, file)

print(f'Reversed routes found: {len(ReversedRoutes)}')
print(f'List saved as {outputJSON}')