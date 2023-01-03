#!/usr/bin/python
from __future__ import print_function
import subprocess
import re
import difflib
import time

def getTables(dbName=None, schemaName=None, tableIncludes=None, server='localhost'):
# returns an alphabetically ordered list of tables belonging to a schema 
# names are converted to lower case to facilitate comparisons between DBMSs 
    if tableIncludes == None:
        # if a schema name has been provided without a table or table file, build an alphbetical list of all tables in the schemas:
        table_select = " SELECT t.relname FROM pg_class t JOIN pg_namespace s ON s.oid = t.relnamespace"           + \
                       " WHERE t.relkind = 'r' AND t.relstorage != 'x'"                                            + \
                       " AND not exists (select '1' from pg_partition_rule part where part.parchildrelid = t.oid)" + \
                       " AND s.nspname = '" + schemaName + "'"                                                     + \
                       " ORDER BY 1;"
    elif len(tableIncludes) == 1:
        # if  a single table value has been provided, then that table is the only one to process:
        # build the select statements:
        table_select = " SELECT t.relname FROM pg_class t JOIN pg_namespace s ON s.oid = t.relnamespace"           + \
                       " WHERE t.relkind = 'r' AND t.relstorage != 'x'"                                            + \
                       " AND not exists (select '1' from pg_partition_rule part where part.parchildrelid = t.oid)" + \
                       " AND s.nspname = '" + schemaName + "'"                                                     + \
                       " AND t.relname = '" + tableIncludes[0] + "'"                                               + \
                       " ORDER BY 1;"
    elif len(tableIncludes) > 1:
        # if more than one table has been included in the requested tables:
        # build the in list:
        table_in_list = "' '"
        for table in tableIncludes:
            table_in_list += ", '" + table + "'"
        # build the select statements:
        table_select = " SELECT t.relname FROM pg_class t JOIN pg_namespace s ON s.oid = t.relnamespace"           + \
                       " WHERE t.relkind = 'r' AND t.relstorage != 'x'"                                            + \
                       " AND not exists (select '1' from pg_partition_rule part where part.parchildrelid = t.oid)" + \
                       " AND s.nspname = '" + schemaName + "'"                                                     + \
                       " AND t.relname in (" + table_in_list + ")"                                                 + \
                       " ORDER BY 1;"
    tablestring = subprocess.Popen(['psql', '-h' + server, '-t', '-d' + dbName, '-c' + table_select], stdout=subprocess.PIPE).communicate()[0]
    tablelist = tablestring.split()
    return tablelist

def triageLists(srcList, tgtList):
#  Compares the list of tables in the source and target table lists, and passes back a list broken into three catagories:
#  - tables defined in the source schema, but not the target schema;
#  - tables defined in the target schema, but not the source schema;
#  - tables defined in both the source and target schemas.
    tgtOnlyList = []
    srcOnlyList = []
    bothList    = []
    # use the difflib utilities to document differences between the two lists:
    deltas = list(difflib.ndiff(srcList, tgtList))
    # triage the tables into the three groups (source-only, target-only, both)
    for line in deltas:
        if line.find("_1_prt_") >= 0:  # table partitions:  ignore
            pass
        elif line[-3:] == '_dr':       # dropped tables:    ignore
            pass
        elif line[0:1] == ' ':         # tables in both
            bothList.append(line[2:])
        elif line[0:1] == '-':         # tables only in the 1st (source) list
            srcOnlyList.append(line[2:])
        elif line[0:1] == '+':         # tables only in the 2nd (target) list
            tgtOnlyList.append(line[2:])
        elif line[0:1] == '?':         # documents where changes start (skip it)
            pass
    # build a dictionary containing the three lists:
    triage_dict = {'srcOnly': srcOnlyList, 'tgtOnly': tgtOnlyList, 'both'   : bothList}
    return triage_dict
    
def getTableList(tablefilename):
#   Reads the requested file of tables, strips out the table names,
#   and returns a sorted list of the table names. 
    if len(tablefilename) == 0:
        print('No Table file specified')
        return None            
    else:
        try:
            tablefile = open(tablefilename, 'r')
        except Exception:
            return -1  
        print('Compare tables file: ' + tablefilename)
        tableList = []
        for table in tablefile:
            tableList.append(table.strip())
        return tableList
        
def getTableDDLs(dbName=None, schemaName=None, tableList=None, server='localhost'):
# calls pg_dump to get a file of ddl syntax for the requested table(s), then splits the results into a dictionary
# of table ddls, where:
#   - the key is the table_name
#   - the value is the CREATE TABLE statement, including any indexes.
    dump_cmd = ['pg_dump', '-sOx', '-h' + server]
    if tableList == None:
        dump_cmd.append("-n" + schemaName)
    else:
        for table in tableList:
            table = table.strip()
            if table != '':
                dump_cmd.append("--table=" + schemaName + "." + table)
    dump_cmd.append(dbName)
    dump_file = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE).communicate()[0]
    # parse the pg_dump output into individual "CREATE ...;" statements:
    parse_tables    = r'(^CREATE TABLE.+?\);$)'
    table_ddls    = re.findall(parse_tables,    dump_file, re.DOTALL|re.MULTILINE)
    # Build a dictionary of the table definitions:
    table_dict = {}
    parse_tablename = r'^CREATE TABLE (.+) \('
    parse_distkey   = r'DISTRIBUTED BY \((.+?)\)'
    parse_partition = r'.*(PARTITION BY .+?);.*'
    parse_single    = r'WITH \((.+?)\) DISTRIBUTED'
    for table in table_ddls:
        # parse out the table definition components:
        table_name      = re.findall(parse_tablename, table)[0]
        table_distkey   = re.findall(parse_distkey, table)
        if table_distkey == []:
            table_distkey = 'randomly'
        else:
            table_distkey = table_distkey[0]
        table_partition = re.findall(parse_partition, table, re.DOTALL|re.MULTILINE)
        if table_partition == []:
            #   Get the single partition information, if any:
            table_partition = re.findall(parse_single, table, re.DOTALL|re.MULTILINE)
            if table_partition == []:
                table_partition = 'single'
            else:
                table_partition = table_partition[0]
        else:
            table_partition = table_partition[0]
        # build a dictionary of components for the table:
        table_dict[table_name]              = {}
        table_dict[table_name]['table']     = table
        table_dict[table_name]['distKey']   = table_distkey
        table_dict[table_name]['partition'] = table_partition
        table_dict[table_name]['indexes']   = {}               # we'll add this next
    # Add the indexes to the table dictionary:
    parse_indexes    = r'(^CREATE(?: UNIQUE)? INDEX.+?\);$)'
    parse_indexname  = r'(?:^.* INDEX) (.*) ON'
    parse_indextable = r'(?:^.* ON) (.*?) '
    index_ddls    = re.findall(parse_indexes,   dump_file, re.DOTALL|re.MULTILINE)
    for index in index_ddls:
        index_name  = re.findall(parse_indexname, index)[0]
        index_table = re.findall(parse_indextable, index)[0]
        table_dict[index_table]['indexes'][index_name] = index
    return table_dict
    # for possible use in the future: 
    #   parse_sequences = r'(^CREATE SEQUENCE.+?;$)'
    #   sequence_ddls = re.findall(parse_sequences, dump_file, re.DOTALL|re.MULTILINE)
    
def compareTables  (srcDef=None, tgtDef=None):
#   Compares the definitions of tables found in both the target and source catalogs,
#   returning a dictionary of if the tables matched, and if not what was mismatched.
    compareResults = {}
    compareResults['tablesMatch'] = True # assume innocent until proven guilty
    #   Compare Columns keys:
    parse_columns  = r'^CREATE TABLE (.+)\n\)' 
    srcCols = re.findall(parse_columns, srcDef['table'], re.DOTALL|re.MULTILINE)[0]
    tgtCols = re.findall(parse_columns, tgtDef['table'], re.DOTALL|re.MULTILINE)[0]    
    if srcCols == tgtCols:
        compareResults['columnsMatch']  = True    
    else:    
        compareResults['columnsMatch']  = False
        compareResults['tablesMatch']   = False
    #   Compare Distribution keys: 
    if srcDef['distKey'] == tgtDef['distKey']:
       compareResults['distKeysMatch']  = True    
    else:    
        compareResults['distKeysMatch'] = False 
        compareResults['tablesMatch']   = False
    #   Compare Partitioning schemes:
    if srcDef['partition'] == tgtDef['partition']:
       compareResults['partDefsMatch']  = True
    else:
        compareResults['partDefsMatch'] = False
        compareResults['tablesMatch']   = False
    #  Compare Indexes:
    srcIndexes = srcDef['indexes'].items().sort()
    tgtIndexes = tgtDef['indexes'].items().sort()
    if srcIndexes == tgtIndexes:
        compareResults['indexesMatch']  = True
    else:
        compareResults['indexesMatch']  = False
        compareResults['tablesMatch']   = False
    return compareResults
 

def getLastUpdate (dbName=None, schemaName=None, tableList=None, server='localhost'):
#   Gets the last update information for a list of tables from the catalog,
#   returning a dictionary of the last update statistics
    #   Build the base dictionary and format the IN list for the list of tables:
    stats      = {}
    tableNames = "''"
    for table in tableList:
        stats[table] = {"actionType":'???', "subActionType":'???', "actionUser":'???', "actionTimestamp":'???'}
        tableNames += ", '" + table + "'"
    #   Build the SQL statement to extract the last-updated statistics:
    statQuery = "SELECT tbl.relname,"                                                      + \
                "    COALESCE(act.staactionname, '???'),"                                  + \
                "    COALESCE(act.stasubtype, '???'),"                                     + \
                "    COALESCE(act.stausename, '???'),"                                     + \
                "    COALESCE(to_char(act.statime, 'YYYY-MM-DD HH24:MM:SS'), '???') "      + \
                "FROM pg_class tbl  "                                                      + \
                "INNER JOIN pg_namespace sch "                                             + \
                "ON (tbl.relnamespace = sch.oid) "                                         + \
                "LEFT OUTER JOIN ( "                                                       + \
                "    SELECT "                                                              + \
                "        objid, "                                                          + \
                "        staactionname, "                                                  + \
                "        stasubtype, "                                                     + \
                "        statime, "                                                        + \
                "        stausename "                                                      + \
                "    FROM pg_stat_last_operation "                                         + \
                "    WHERE staactionname IN ('CREATE', 'ALTER', 'DROP') "                  + \
                "      AND stasubtype <> 'OWNER' "                                         + \
                "    ) act "                                                               + \
                "ON (act.objid = tbl.oid) "                                                + \
                "WHERE sch.nspname = '" + schemaName + "'"                                 + \
                "  AND tbl.relname IN (" + tableNames + ")"                                + \
                "  AND tbl.relkind in ('r', 'i', 'v', 'S', 'c') "                          + \
                "ORDER BY sch.nspname, tbl.relname, act.statime "                          + \
                ";"
    statString = subprocess.Popen(['psql', '-t', '-h' + server, '-d' + dbName, '-c' + statQuery], stdout=subprocess.PIPE).communicate()[0]
    statList = statString.split('\n')
    for line in statList:
        statEntry = line.split('|')
        table = statEntry[0].strip()
        if len(table) > 0:
            if len(statEntry) > 0:
                stats[table]["actionType"]      = statEntry[1].strip()
            if len(statEntry) > 1:
                stats[table]["subActionType"]   = statEntry[2].strip()
            if len(statEntry) > 2:
                stats[table]["actionUser"]      = statEntry[3].strip()
            if len(statEntry) > 3:
                stats[table]["actionTimestamp"] = statEntry[4].strip()
    return stats
    
def getMismatchDetails(srcDef=None, tgtDef=None):
#   Creates a listing of the differences between the source and table definitions,
#   using the python difflib comparision functions.
    #   Build CREATE TABLE detailed comparison:
    tableDeltas = list(difflib.ndiff(srcDef['table'].split('\n'), tgtDef['table'].split('\n')))
    #  Indexes must all match exactly:
    srcIndexes = [srcDef['indexes'].items().sort()]
    if srcIndexes == [None]:
        srcIndexes = ['No indexes']
    tgtIndexes = [tgtDef['indexes'].items().sort()]
    if tgtIndexes == [None]:
        tgtIndexes = ['No indexes']
    indexDeltas = list(difflib.ndiff(srcIndexes, tgtIndexes))
    mismatchDetails = tableDeltas + ["\n"] + indexDeltas
    return mismatchDetails
 
                
def buildComparisonReport(srcDbName=None, srcSchemaName=None, srcServer='localhost', tgtDbName=None, tgtSchemaName=None, tgtServer='localhost', tableIncludes=None, compareFileName=None):
#   This is the main driver for the program.
#     
#   It calls subroutines to:
    if compareFileName == None:
    #  Build the report file name
        compareFileName = "Compare_" + srcSchemaName + "_to_" + tgtSchemaName + "_on_" + time.strftime("%Y-%m-%d") + ".txt"
    #  Build a list of the tables of interest in the source and target environments
    print("Building lists of tables to compare")
    srcTables = getTables (dbName=srcDbName, schemaName=srcSchemaName, server=srcServer, tableIncludes=tableIncludes);
    tgtTables = getTables (dbName=tgtDbName, schemaName=tgtSchemaName, server=tgtServer, tableIncludes=tableIncludes);
    #  Split the lists of tables into three groups:
    #   - tables only in the source environment;
    #   - tables only in the target environment;
    #   - tables that are in both the source and target environments (these are the most interesting ones).
    print("Splitting tables into source only, target only, or both")
    triage_dict = triageLists(srcTables, tgtTables);
    missingTables = triage_dict['srcOnly'];
    extraTables   = triage_dict['tgtOnly'];
    cmprTables    = triage_dict['both'];
    #  Get the DDL statements for the tables that exist in both source and target enviroments:
    print("Getting source table definitions")
    srcDDL = getTableDDLs (dbName=srcDbName, schemaName=srcSchemaName, server=srcServer, tableList=cmprTables);
    print("Getting target table definitions")
    tgtDDL = getTableDDLs (dbName=tgtDbName, schemaName=tgtSchemaName, server=tgtServer, tableList=cmprTables);
    #   Compare source and target definitions for each of the table found in both environments:
    matchedTables    = [];
    mismatchedTables = [];  # List of tables that mismatch 
    mismatchedKeys   = {};  # A dictionary of what didn't match for each table
    print("Comparing tables")
    for table in cmprTables:
        print("    ... " + table)
        mismatchedKeys [table] = {}
        compareResults = compareTables(srcDef=srcDDL[table], tgtDef=tgtDDL[table])
        if compareResults['tablesMatch'] == True:
            matchedTables += [table]
        else:
            mismatchedTables      += [table]
            mismatchedKeys[table] = compareResults
    ####   At this point, we can start assembling the report. ###
    #   Compute the summary statistics:
    missing_table_count  = len(missingTables)
    extra_table_count    = len(extraTables)
    matching_table_count = len(matchedTables)
    mismatch_table_count = len(mismatchedTables)
    total_tables = missing_table_count + extra_table_count + matching_table_count + mismatch_table_count
    #   Publish the summary:
    comparefile = open(compareFileName, 'w')
    heading = "Comparison of " + srcSchemaName + " in " + srcDbName + " to " + tgtSchemaName + " in " + tgtDbName + " on " + time.strftime("%Y-%m-%d")
    summary = "\n    Compared: " +  str(total_tables) + "; matches: " + str(matching_table_count) + "; missing: " + str(missing_table_count) + "; extra: " + str(extra_table_count) + "; mismatched: " + str(mismatch_table_count)
    print(heading, file=comparefile)
    print(summary, file=comparefile)
    print("\n",    file=comparefile)
    #   Publish the list of matching tables:
    heading = "Tables in " + tgtSchemaName + " in " + tgtDbName + " that match " + srcSchemaName + " in " + srcDbName + ":\n"
    if matching_table_count == 0:
        print("    No matched tables\n", file=comparefile)
    else: 
        print(heading, file=comparefile)
        for table in matchedTables:
            print("    " + table, file=comparefile)
    print("\n", file=comparefile)
    #   Publish the list of tables missing from the target database:
    heading = "Tables that are missing from " + tgtSchemaName + " in " + tgtDbName + ":\n"
    if len(missingTables) == 0:
        print("    No Missing tables\n", file=comparefile)
    else: 
        print(heading, file=comparefile)
        srcStats = getLastUpdate(dbName=srcDbName, schemaName=srcSchemaName, tableList=missingTables, server=srcServer)
        for table in missingTables:
            if srcStats[table] == None:
               srcTimestamp = "???"
            else:                
               srcTimestamp = srcStats[table]["actionTimestamp"]    
               srcUpdated   = srcStats[table]["actionUser"]
            print("    " + table.ljust(50) + "\t\t(last updated on " + srcTimestamp  + " by " + srcUpdated + ")", file=comparefile)
        print("\n", file=comparefile)

    #   Publish the list of extra tables in the target database:
    heading = "Extra Tables in " + tgtSchemaName + " in " + tgtDbName + ":\n"
    if extra_table_count == 0:
        print("    No Extra tables\n", file=comparefile)
    else:
        print(heading, file=comparefile)
        tgtStats = getLastUpdate(dbName=tgtDbName, schemaName=tgtSchemaName, tableList=extraTables, server=tgtServer)
        for table in extraTables:
            if tgtStats == None:
               tgtTimestamp = "???"
            else:
               tgtTimestamp = tgtStats[table]["actionTimestamp"]
               tgtUpdated   = tgtStats[table]["actionUser"]
            print("  " + table.ljust(50) + "\t\t(last updated on " + tgtTimestamp + " by " + tgtUpdated + ")", file=comparefile)
        print("\n", file=comparefile)

    #   Publish the list of mismatched tables:
    heading = "Tables in " + tgtDbName + " in " + tgtSchemaName + " that do no match " + srcSchemaName + " in " + srcDbName + ":\n"
    if mismatch_table_count == 0:
        print("    No mismatched tables\n", file=comparefile)
    else:
        print(heading, file=comparefile)
        print("  Legend:", file=comparefile)
        print("    - value in source table", file=comparefile)
        print("    + value in target table", file=comparefile)
        print("    ? location of difference (look for ^)", file=comparefile) 
        srcStats = getLastUpdate (dbName=srcDbName, schemaName=srcSchemaName, tableList=mismatchedTables, server=srcServer)
        tgtStats = getLastUpdate (dbName=tgtDbName, schemaName=tgtSchemaName, tableList=mismatchedTables, server=tgtServer)
        for table in mismatchedTables:
            print(" processing " + table)
            #   Print the header for the mismatched table:
            if srcStats[table] == None:
                srcTimestamp = "???"
            else:                
                srcTimestamp = srcStats[table]["actionTimestamp"]
                srcUpdated   = srcStats[table]["actionUser"]
            if tgtStats[table] == None:
                tgtTimestamp = "???"
            else:
                tgtTimestamp = tgtStats[table]["actionTimestamp"]
                tgtUpdated   = tgtStats[table]["actionUser"]
            table_header = "\n" + table.ljust(50) + "\t\t(last updated in " + srcSchemaName + " on " + srcTimestamp + " by " + srcUpdated + "; " + tgtSchemaName + " on " + tgtTimestamp + " by " + tgtUpdated + "):"
            if srcTimestamp < tgtTimestamp:
                table_header += "\t!!! Stale Updates !!!"
            print(table_header, file=comparefile)
            
            distKeysMatch = mismatchedKeys[table]["distKeysMatch"]
            partDefsMatch = mismatchedKeys[table]["partDefsMatch"]
            indexesMatch  = mismatchedKeys[table]["indexesMatch"]
            columnsMatch  = mismatchedKeys[table]["columnsMatch"]
            summary = "\n  Distribution keys match? " + str(distKeysMatch) + ";  Partition keys match? " + str(partDefsMatch) + ";  Indexes match? " + str(indexesMatch) + ";  Columns match? " + str(columnsMatch)

            #   Build out the details for the tables that don't match:
            details = getMismatchDetails(srcDef=srcDDL[table], tgtDef=tgtDDL[table])
            for detail in details:
                print("  " + detail, file=comparefile) 
    print("\n", file=comparefile)
    # wrap-up:
    comparefile.close()
    return

if __name__ == "__main__":
    srcDbName='codpft';
    srcSchemaName='codpft001';
    srcServer='localhost';
    tgtDbName='codprod';
    tgtSchemaName='codprd';
    tgtServer='lneddgp211';
    tableIncludes=None;
    buildComparisonReport(srcDbName=srcDbName, srcSchemaName=srcSchemaName, tgtDbName=tgtDbName, tgtSchemaName=tgtSchemaName, tgtServer=tgtServer, tableIncludes=None)
    