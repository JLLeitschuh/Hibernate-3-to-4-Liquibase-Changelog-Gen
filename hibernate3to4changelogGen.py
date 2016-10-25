#!/usr/bin/env python

import argparse
import sys
import os
import xml.etree.ElementTree as ET
import StringIO
import xml.dom.minidom
import getpass

XML_NAMESPACE = {
    'node': 'http://www.liquibase.org/xml/ns/dbchangelog'
}


def dict_to_sorted_list(dict):
    d = dict.items()
    d.sort()
    return d


def flatten(list_of_lists):
    return [val for sublist in list_of_lists for val in sublist]


def xml_line_to_dict(xmlLine):
    """
    >>> dict = xml_line_to_dict('<addUniqueConstraint columnNames="uuid, macaddress, vlan" constraintName="attachednetworkdevicejpa_uuid_macaddress_vlan_key" deferrable="false" disabled="false" initiallyDeferred="false" tableName="attachednetworkdevicejpa"/>')
    >>> dict_to_sorted_list(dict)
    [('columnNames', 'uuid, macaddress, vlan'), ('constraintName', 'attachednetworkdevicejpa_uuid_macaddress_vlan_key'), ('deferrable', 'false'), ('disabled', 'false'), ('initiallyDeferred', 'false'), ('tableName', 'attachednetworkdevicejpa')]

    :param xmlLine:
    :return:
    """
    return ET.fromstring(xmlLine).attrib


def make_file_relative(path):
    """
    >>> make_file_relative('com/company/core/db/changelog/db.changelog-1.1.0.xml')
    'db.changelog-1.1.0.xml'
    >>> make_file_relative('com/company/core/db/changelog/db.changelog-master.xml')
    'db.changelog-master.xml'
    >>> make_file_relative('db.changelog-master.xml')
    'db.changelog-master.xml'

    :param path: The path that is defined relative to this directory
    :return: The file name with the path made relative to this directory.
    """
    head, tail = os.path.split(path)
    return tail


def get_inner_imported_files(root):
    """
    :param root: The root node of an XML file
    :return: A list of all of the files to import relative to this directory
    """
    return [make_file_relative(child.attrib['file'])
            for child in root.findall("./node:include", XML_NAMESPACE)]


def parse_file_to_xml(file):
    """"
    Parses an input file into XML.
    """
    return ET.parse(file).getroot()


def to_drop_constraint_version(dict):
    return {'constraintName': dict['constraintName'], 'tableName': dict['tableName']}


def adds_to_add_drop_constraints(masterConstraints, newConstraints):
    """
    >>> masterConstraints = {'columnNames': "uuid, macaddress, vlan", 'constraintName': "attachednetworkdevicejpa_uuid_macaddress_vlan_key", 'deferrable': "false", 'disabled':"false", 'initiallyDeferred':"false", 'tableName':"attachednetworkdevicejpa"}
    >>> newConstraints = {'columnNames': "uuid, macaddress, vlan", 'constraintName': "uk_2o0nn8nq8eoo40bpyyq5k9anh", 'tableName':"attachednetworkdevicejpa"}
    >>> drop, add = adds_to_add_drop_constraints(masterConstraints, newConstraints)
    >>> dict_to_sorted_list(drop)
    [('constraintName', 'attachednetworkdevicejpa_uuid_macaddress_vlan_key'), ('tableName', 'attachednetworkdevicejpa')]
    >>> dict_to_sorted_list(add)
    [('columnNames', 'uuid, macaddress, vlan'), ('constraintName', 'uk_2o0nn8nq8eoo40bpyyq5k9anh'), ('deferrable', 'false'), ('disabled', 'false'), ('initiallyDeferred', 'false'), ('tableName', 'attachednetworkdevicejpa')]

    >>> masterConstraints = xml_line_to_dict('<addUniqueConstraint columnNames="uuid" constraintName="externalgatewayjpa_uuid_key" deferrable="false" disabled="false" initiallyDeferred="false" tableName="externalgatewayjpa"/>')
    >>> newConstraints = xml_line_to_dict('<addUniqueConstraint columnNames="uuid" constraintName="uk_2pqcv4b75ribau4in54ppmyuu" tableName="externalgatewayjpa"/>')
    >>> drop, add = adds_to_add_drop_constraints(masterConstraints, newConstraints)
    >>> dict_to_sorted_list(drop)
    [('constraintName', 'externalgatewayjpa_uuid_key'), ('tableName', 'externalgatewayjpa')]
    >>> dict_to_sorted_list(add)
    [('columnNames', 'uuid'), ('constraintName', 'uk_2pqcv4b75ribau4in54ppmyuu'), ('deferrable', 'false'), ('disabled', 'false'), ('initiallyDeferred', 'false'), ('tableName', 'externalgatewayjpa')]

    :param masterConstraints: The add constraint that are from the master changelog
    :param newConstraints: The constraint for the same column name in the same table from the base change-set
    :return: (drop, add) The tuple to generate the drop then the add lines for the changelog
    """
    assert masterConstraints['columnNames'] == newConstraints['columnNames']
    assert masterConstraints['tableName'] == newConstraints['tableName']
    return to_drop_constraint_version(masterConstraints), \
           {'columnNames': masterConstraints['columnNames'], 'constraintName': newConstraints['constraintName'],
            'deferrable': "false", 'disabled': "false", 'initiallyDeferred': "false",
            'tableName': masterConstraints['tableName']}

def get_all_properties(root):
    return [child.attrib for child in root.findall("./node:property", XML_NAMESPACE)]

def get_all_unique_constraint_additions(root):
    return [child.attrib for child in root.findall("./node:changeSet/node:addUniqueConstraint", XML_NAMESPACE)]


def get_all_unique_constraint_drops(root):
    return [child.attrib for child in root.findall("./node:changeSet/node:dropUniqueConstraint", XML_NAMESPACE)]


def remove_dropped_adds(additions, drops):
    """
    >>> addition1 = {'columnNames': 'foreignuuid', 'constraintName': 'ethertypeinternalaffinityelementjpa_foreignuuid_key', 'tableName': 'ethertypeinternalaffinityelementjpa'}
    >>> addition2 = {'columnNames': 'uuid', 'constraintName': 'ethertypeinternalaffinityelementjpa_uuid_key', 'tableName': 'ethertypeinternalaffinityelementjpa'}
    >>> removal = {'constraintName': 'ethertypeinternalaffinityelementjpa_uuid_key', 'tableName': 'ethertypeinternalaffinityelementjpa'}
    >>> len(remove_dropped_adds([addition1, addition2], [removal]))
    1
    >>> len(remove_dropped_adds([addition1, addition2], []))
    2

    :param additions:
    :param drops:
    :return:
    """
    return [addition for addition in additions
            if to_drop_constraint_version(addition) not in drops]


def merge_master_adds_and_new_adds(master_list, new_list):
    return [(master, new)
            for master in master_list
            for new in new_list
            if master['tableName'] == new['tableName']
            and master['columnNames'] == new['columnNames']
            # no need to add a constraint change that already exists
            and master['constraintName'] != new['constraintName']]

def add_and_removes_to_changelog_xml(add_and_removes, properties, change_id):
    ns = {'xmlns': "http://www.liquibase.org/xml/ns/dbchangelog", 'xmlns:ext': "http://www.liquibase.org/xml/ns/dbchangelog-ext", 'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance", 'xsi:schemaLocation': "http://www.liquibase.org/xml/ns/dbchangelog-ext http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-ext.xsd http://www.liquibase.org/xml/ns/dbchangelog http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-3.4.xsd"}
    top = ET.Element('databaseChangeLog', ns)
    for prop in properties:
        ET.SubElement(top, 'property', prop)
    change_set = ET.SubElement(top, 'changeSet', {'author': getpass.getuser(), 'id': change_id})
    ET.SubElement(change_set, 'comment')\
        .text = """
            Constraint naming convention was changed between Hibernate 3 and 4.
            This XML was generated using the `hibernate3to4changelogGen.py` file.
        """
    for (drop, add) in add_and_removes:
        ET.SubElement(change_set, 'dropUniqueConstraint', drop)
        ET.SubElement(change_set, 'addUniqueConstraint', add)
    modify_sql = ET.SubElement(change_set, 'modifySql', {'dbms': 'postgresql'})
    ET.SubElement(modify_sql, 'replace', {'replace': "WITH", 'with': "WITHOUT"})
    return top



parser = argparse.ArgumentParser(
    description='Process db.changelog-master and the current changelog to generate key constraint changes in liquibase')
parser.add_argument('changelog',
                    metavar='C', type=argparse.FileType('r'),
                    # default=sys.stdin,
                    help='The base changelog for this branch (not db.changelog-master.xml)')
parser.add_argument('output',
                    metavar='O', type=argparse.FileType('w'),
                    default=sys.stdout,
                    help='The output file for this changeset (not db.changelog-master.xml)')
parser.add_argument('change_id',
                    metavar='ID', type=str,
                    help='The changeset id to be used on this generated change')

parser.add_argument('--test', action='store_true', help='Run all of the tests in the script')

if '--test' in sys.argv:
    # This can't be done through argparse because it will require all input flags to be set
    import doctest

    doctest.testmod(verbose=True)
else:
    args = parser.parse_args()

    print args.changelog
    imported = get_inner_imported_files(parse_file_to_xml('db.changelog-master.xml'))
    changelog_xml = parse_file_to_xml(args.changelog)
    properties = get_all_properties(changelog_xml)

    new_constraints = get_all_unique_constraint_additions(changelog_xml)

    adds = flatten([get_all_unique_constraint_additions(parse_file_to_xml(importMe)) for importMe in imported])
    drops = flatten([get_all_unique_constraint_drops(parse_file_to_xml(importMe)) for importMe in imported])
    filtered = remove_dropped_adds(adds, drops)
    import pprint
    pp = pprint.PrettyPrinter(indent=2)

    all_adds = merge_master_adds_and_new_adds(filtered, new_constraints)
    xml_diff = [adds_to_add_drop_constraints(master, new) for (master, new) in all_adds]

    pp.pprint(xml_diff)

    output_xml = add_and_removes_to_changelog_xml(xml_diff, properties, args.change_id)
    tree = ET.ElementTree(output_xml)
    output = StringIO.StringIO()
    tree.write(output, xml_declaration=True, encoding='UTF-8')
    reparsed = xml.dom.minidom.parseString(output.getvalue())
    output.close()
    args.output.write(reparsed.toprettyxml(indent="    "))


    # print [constraint for constraint in constraints if 'uk_' not in constraint['constraintName']]
