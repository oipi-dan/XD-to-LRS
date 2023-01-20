import arcpy
from xd_to_rns import compare_route_name_similarity

lrs = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Data\ProjectedInput.gdb\LRS'


rteA = 'R-VA   SR00195SB'
rteB = 'R-VA   IS00195SB'

print(rteA, rteB)
print(compare_route_name_similarity(rteA, rteB, lrs))

rteA = 'R-VA   IS00195NB'
rteB = 'R-VA   IS00195SB'
print(rteA, rteB)
print(compare_route_name_similarity(rteA, rteB, lrs))

rteA = 'R-VA   IS00192NB'
rteB = 'R-VA   IS00195SB'
print(rteA, rteB)
print(compare_route_name_similarity(rteA, rteB, lrs))