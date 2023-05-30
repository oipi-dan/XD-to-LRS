import arcpy
import os
from xd_to_rns import run_conflation
import sys
from datetime import datetime

# Enter input variables
inputXD = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\USA_Virginia'
inputMasterLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'
inputOverlapLRS = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_OVERLAP'
inputIntersections = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS_intersections'

conflationName = 'Batch_11'
outputPath = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Output'
xdFliter = "Batch = 11"


def start(inputXD, inputMasterLRS, inputOverlapLRS, inputIntersections, conflationName, outputPath, xdFliter):
    # Create output gdb
    if os.path.exists(outputPath):
        arcpy.env.overwriteOutput = True
        outputGDBPath = f'{outputPath}\{conflationName}.gdb'
        if not os.path.exists(outputGDBPath):
            print('Creating output gdb')
            arcpy.CreateFileGDB_management(outputPath, f'{conflationName}.gdb')

        

    # Run initial conflation
    print('\n### Running initial conflation ###\n')
    
    outputCSV_initial = f'Output/{conflationName}_initial.csv'
    run_conflation(conflationName, outputCSV_initial, inputXD, inputMasterLRS, inputIntersections, xdFliter, lrsFilter='', printProgress=False)

    # Create initial conflation event layer
    print('\n### Creating initial conflation event layer ###\n')
    arcpy.MakeRouteEventLayer_lr(inputMasterLRS, 'RTE_NM', outputCSV_initial, "RTE_NM; Line; BEGIN_MSR; END_MSR", "initialEvents")
    arcpy.FeatureClassToFeatureClass_conversion("initialEvents", outputGDBPath, f'{conflationName}_initial')

    # Flip routes
    print('\n### Flipping Routes ###\n')
    from flipRoutes import run_flip_routes
    inputEvents = f'{outputPath}\{conflationName}.gdb\{conflationName}_initial'
    outputCSV_flipped = f'Output/{conflationName}_flipped.csv'
    run_flip_routes(conflationName, inputEvents, outputCSV_flipped, inputXD, inputOverlapLRS)



    # Create flipped event layer
    print('\n### Creating flipped conflation event layer ###\n')
    arcpy.MakeRouteEventLayer_lr(inputOverlapLRS, 'RTE_NM', outputCSV_flipped, "RTE_NM; Line; BEGIN_MSR; END_MSR", "flippedEvents")
    arcpy.FeatureClassToFeatureClass_conversion("flippedEvents", outputGDBPath, f'{conflationName}')

    # Run autoQC
    from AutoQC import run_AutoQC
    print('\n### AutoQC ###\n')
    outputCSV_QC = f'Output/{conflationName}_QC.csv'
    run_AutoQC(conflationName, inputXD, f'{outputPath}\{conflationName}.gdb\{conflationName}', outputCSV_QC)


if __name__ == '__main__':
    args = sys.argv
    if len(args) > 1:
        inputXD = args[1]
        inputMasterLRS = args[2]
        inputOverlapLRS = args[3]
        inputIntersections = args[4]
        outputPath = args[5]
        conflationName = args[6]
        xdFliter = args[7]

        startTime = datetime.now()
        start(inputXD, inputMasterLRS, inputOverlapLRS, inputIntersections, conflationName, outputPath, xdFliter)
        endTime = datetime.now()

        with open('test.txt', 'a') as file:
            file.write(f'{endTime - startTime}\n')
    else:
        start(inputXD, inputMasterLRS, inputOverlapLRS, inputIntersections, conflationName, outputPath, xdFliter)