""" These are functions to paste into Pro's python window to aid in QC """

XDLayer = ''
OutputLayer = ''

def set_df(layerName, sql):
    prj = arcpy.mp.ArcGISProject('CURRENT')
    map = prj.listMaps()[0]
    layer = map.listLayers(layerName)[0]
    
    layer.definitionQuery = sql

def sd(xd=''):
    if xd == '':
        set_df(XDLayer, '')
        set_df(OutputLayer, '')
    else:
        set_df(XDLayer, f"XDSegID = '{xd}'")
        set_df(OutputLayer, f"XDSegID = {xd}")
        zoom_to_layer(XDLayer)

def zoom_to_layer(layerName):
    """ Zooms to the selected features of the input layer.  The layerName
        attribute is a string representing the layer name as it appears
        in the table of contents 
        
        Important caveat - the Map tab must be selected for this to work
        (if something else like the attributes table is active, it will return
        an error).  This is a built-in limitation of arcpy. """
    prj = arcpy.mp.ArcGISProject("CURRENT")
    map = prj.listMaps()[0]

    mapView = prj.activeView
    camera = mapView.camera

    layer = map.listLayers(layerName)[0]
    newExtent = mapView.getLayerExtent(layer)
    camera.setExtent(newExtent)