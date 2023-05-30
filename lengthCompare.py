def compare_lengths(XDLayer, ConflationLayer):
    # Get XD Lengths in Miles and put in dictionary
    print('Creating XDLenDict')
    XDLenDict = {}
    with arcpy.da.SearchCursor(XDLayer, ['XDSegID','SHAPE@']) as cur:
        for row in cur:
            len = row[1].getLength('GEODESIC', 'MILES')
            XDLenDict[int(row[0])] = len

    # Add fields to ConflationLayer
    fields = arcpy.ListFields(ConflationLayer)
    if 'XDLen' not in fields:
        print(f'Adding field XDLen')
        arcpy.AddField_management(ConflationLayer, 'XDLen', 'DOUBLE')
    if 'ConflationLen' not in fields:
        print(f'Adding field ConflationLen')
        arcpy.AddField_management(ConflationLayer, 'ConflationLen', 'DOUBLE')
    if 'ConflationTotalLen' not in fields:
        print(f'Adding field ConflationTotalLen')
        arcpy.AddField_management(ConflationLayer, 'ConflationTotalLen', 'DOUBLE')
    if 'LenDiff' not in fields:
        print(f'Adding field LenDiff')
        arcpy.AddField_management(ConflationLayer, 'LenDiff', 'DOUBLE')

    # Calculate conflation layer lengths
    print('Calcualting conflation layer lengths')
    with arcpy.da.UpdateCursor(ConflationLayer, ['XDSegID', 'ConflationLen', 'SHAPE@']) as cur:
        for row in cur:
            try:
                len = row[2].getLength('GEODESIC', 'MILES')
                row[1] = len
                cur.updateRow(row)
            except:
                continue

    print('Adding conflation total lengths')
    XDTotalDicts = {int(row[0]):[] for row in arcpy.da.SearchCursor(XDLayer, 'XDSegID')}
    with arcpy.da.SearchCursor(ConflationLayer, ['XDSegID', 'ConflationLen']) as cur:
        for row in cur:
            if row[1] is not None:
                XDTotalDicts[row[0]].append(row[1])
    
    with arcpy.da.UpdateCursor(ConflationLayer, ['XDSegID', 'ConflationTotalLen']) as cur:
        for row in cur:
            row[1] = sum(XDTotalDicts[row[0]])
            cur.updateRow(row)


    # Add XD Lengths
    print('Adding XD Lengths')
    with arcpy.da.UpdateCursor(ConflationLayer, ['XDSegID', 'XDLen']) as cur:
        for row in cur:
            row[1] = XDLenDict[row[0]]
            cur.updateRow(row)


    # Calculate len differences
    print('Calculating len difference')
    with arcpy.da.UpdateCursor(ConflationLayer, ['ConflationTotalLen', 'XDLen', 'LenDiff']) as cur:
        for row in cur:
            row[2] = abs(row[0] - row[1])
            cur.updateRow(row)