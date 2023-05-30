import arcpy
import pandas as pd

def count_mileage_XD(districts, layer):
    output = []

    with arcpy.da.SearchCursor(districts, ['DISTRICT_N', 'SHAPE@']) as cur:
        for row in cur:
            arcpy.management.SelectLayerByLocation(layer, 'INTERSECT', row[1])
            lengths = []
            with arcpy.da.SearchCursor(layer, ['BEGIN_MSR','END_MSR']) as cur:
                for begin, end in cur:
                    if begin and end:
                        length = abs(end-begin)
                        lengths.append(length)
            output.append((row[0], round(sum(lengths))))
    
    df = pd.DataFrame(output, columns=['District','Miles'])
    df = df.sort_values(by=['Miles'], ascending=False)
    print(df)

def count_mileage_TMC(districts, layer):
    output = []

    with arcpy.da.SearchCursor(districts, ['DISTRICT_N', 'SHAPE@']) as cur:
        for row in cur:
            arcpy.management.SelectLayerByLocation(layer, 'INTERSECT', row[1])
            lengths = []
            with arcpy.da.SearchCursor(layer, ['STARTMILEP','ENDMILEPOI']) as cur:
                for begin, end in cur:
                    if begin and end:
                        length = abs(end-begin)
                        lengths.append(length)
            output.append((row[0], round(sum(lengths))))
    
    df = pd.DataFrame(output, columns=['District','Miles'])
    df = df.sort_values(by=['Miles'], ascending=False)
    print(df)