#!/usr/bin/env python
# encoding: utf-8
import copy
import npyscreen

srcdbname = ''
srcserver = ''
srcschema = ''
tgtdbname = ''
tgtserver = ''
tgtschema = ''

def set_srcserver(server): srcserver = server
def set_srcdbname(dbname): srcdbname = dbname
def set_srcschema(schema): srcschema = schema

def get_srcserver(): return srcserver
def get_srcdbname(): return srcdbname
def get_srcschema(): return srcschema

def set_tgtserver(server): tgtserver = server
def set_tgtdbname(dbname): tgtdbname = dbname
def set_tgtschema(schema): tgtschema = schema

def get_tgtserver(): return tgtserver
def get_tgtdbname(): return tgtdbname
def get_tgtschema(): return tgtschema

def build_schema_list(servername, dbname):
#  Builds a list of application schemas for the requested database: 
    values = []
    if dbname == 'coddev':
        values = ['codcct001']
    elif dbname == 'codat':
        values = ['codat012','codat102']
    elif dbname == 'codpt':
        values = ['codpdt001','codpdt013']
    elif dbname == 'codpft':
        values = ['codpft001','codpft998','codpft999']
    elif dbname == 'codprod':
        values = ['codprd']
    return values
    
def update_source_schemas(widget):
    selection = widget.get_selected_objects()
    if selection:
        dbname = selection[0].split()[0]
        set_srcdbname(dbname)
        servername = selection[0].split()[1].strip('()')
        set_srcserver(servername)
        values = build_schema_list(servername, dbname)
        widget.parent.parentApp.getForm('MAIN').srcschemas.values = copy.deepcopy(values)
        widget.parent.parentApp.getForm('MAIN').display()    
    
def update_target_schemas(widget):
    selection = widget.get_selected_objects()
    if selection:
        dbname = selection[0].split()[0]
        set_tgtdbname(dbname)
        servername = selection[0].split()[1].strip('()')
        set_tgtserver(servername)
        values = build_schema_list(servername, dbname)
        widget.parent.parentApp.getForm('MAIN').tgtschemas.values = copy.deepcopy(values)
        widget.parent.parentApp.getForm('MAIN').display()

def get_source_schema(widget):
    selection = widget.get_selected_objects()
    if selection:
        set_srcschema(selection[0].split()[0])
        
def get_target_schema(widget):
    selection = widget.get_selected_objects()
    if selection:
        set_tgtschema(selection[0].split()[0])
        
class BoxCxn(npyscreen.BoxTitle):
    _contained_widget = npyscreen.SelectOne
    
class gpCompareMainForm(npyscreen.Form):

    def afterEditing(self):
        self.parentApp.setNextForm(None)

    def create(self):

        srcdb           = self.add(npyscreen.TitleSelectOne, scroll_exit=True, name = "Source Database:", relx=2,  rely=2,  max_width=30, max_height=7, value_changed_callback=update_source_schemas)
        self.srcschemas = self.add(npyscreen.TitleSelectOne, scroll_exit=True, name='Source Schema:',     relx=2,  rely=9,  max_width=35, max_height=7, value_changed_callback=get_source_schema)
        srcdb.values = ["coddev  (lneddgt405)", "codat   (lneddgt405)", "codpt   (lneddgt405)", "codpft  (lneddgt405)", "codprod (lneddgp211)"]
        self.srcschemas.values = ['...']

        tgtdb           = self.add(npyscreen.TitleSelectOne, scroll_exit=True, name = "Target Database:", relx=40, rely=2,  max_width=30, max_height=7, value_changed_callback=update_target_schemas)
        self.tgtschemas = self.add(npyscreen.TitleSelectOne, scroll_exit=True, name='Target Schema:',     relx=40, rely=9,  max_width=35, max_height=7, value_changed_callback=get_target_schema)
        tgtdb.values = srcdb.values
        self.tgtschemas.values = ['...']
        
        
        
class gpCompareApp(npyscreen.NPSAppManaged):
    def onStart(self):
        self.addForm('MAIN', gpCompareMainForm, name='Greenplum Table Comparison')

if __name__ == '__main__':
    gpCompareApp = gpCompareApp().run()