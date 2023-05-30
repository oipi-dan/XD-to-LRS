import arcpy
import pandas as pd


inputevents = r'C:\Users\daniel.fourquet\Documents\Tasks\XD-to-LRS\Output\FinalBatches.gdb\FinalBatches_1'

EventDict = {row[0]:[] for row in arcpy.da.SearchCursor(inputevents, 'RTE_NM')}

with arcpy.da.SearchCursor(inputevents, ['XDSegID', 'RTE_NM','BEGIN_MSR','END_MSR']) as cur:
    for XDSegID, RTE_NM, BEGIN_MSR, END_MSR in cur:
        try:

            EventDict[RTE_NM].append((BEGIN_MSR, END_MSR))
        except:
            continue

overlaps = []

with arcpy.da.SearchCursor(inputevents, ['XDSegID', 'RTE_NM','BEGIN_MSR','END_MSR']) as cur:
    for XDSegID, RTE_NM, BEGIN_MSR, END_MSR in cur:
        try:

            events = EventDict[RTE_NM]
            overlapCount = 0
            for event in events:
                if BEGIN_MSR >= event[0] and END_MSR <= event[1]:
                    overlapCount += 1
            if overlapCount > 1:
                overlaps.append((XDSegID, RTE_NM, BEGIN_MSR, END_MSR))
        except:
            continue

df = pd.DataFrame(overlaps, columns=['XDSegID','RTE_NM','Begin_Msr','End_Msr'])
df.to_csv('overlappingEvents.csv',index=False)
print(len(overlaps))