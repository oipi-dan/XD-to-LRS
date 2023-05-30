set inputXD="Data\ProjectedInput.gdb\USA_Virginia"
set inputMasterLRS="Data\ProjectedInput.gdb\LRS"
set inputOverlapLRS="Data\ProjectedInput.gdb\LRS_OVERLAP"
set inputIntersections="Data\ProjectedInput.gdb\LRS_intersections"
set outputPath="Output"

set conflationName="Batch_4"
set xdFliter="Batch = 4"
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" RunConflation.py %inputXD% %inputMasterLRS% %inputOverlapLRS% %inputIntersections% %outputPath% %conflationName% %xdFliter%

set conflationName="Batch_5"
set xdFliter="Batch = 5"
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" RunConflation.py %inputXD% %inputMasterLRS% %inputOverlapLRS% %inputIntersections% %outputPath% %conflationName% %xdFliter%

set conflationName="Batch_6"
set xdFliter="Batch = 6"
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" RunConflation.py %inputXD% %inputMasterLRS% %inputOverlapLRS% %inputIntersections% %outputPath% %conflationName% %xdFliter%

set conflationName="Batch_10"
set xdFliter="Batch = 10"
"C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" RunConflation.py %inputXD% %inputMasterLRS% %inputOverlapLRS% %inputIntersections% %outputPath% %conflationName% %xdFliter%

pause