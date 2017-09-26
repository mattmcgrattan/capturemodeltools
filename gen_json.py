import os
import urllib
# noinspection PyCompatibility
import urlparse
import argparse
import yaml
import requests
import logging
import json
from jinja2 import Template
from collections import OrderedDict
import unicodecsv as csv
import ontospy

# global namespace lookup
with open('context.json', 'r') as c:
    namespaces = json.load(c)['@context']


def get_uri(uri):
    """
    Get text from a URI
    :param uri: uri (can be file://, or http(s)://
    :return: text or None
    """
    if uri.startswith('file://'):
        f = urllib.url2pathname(urlparse.urlparse(uri).path)
        if os.access(f, os.R_OK):
            with open(f) as file_f:
                text = file_f.read()
                return text
        else:
            logging.warning('WARNING Cannot read: %s', uri)
            return None
    elif uri.startswith(('http://', 'https://')):
        r = requests.get(uri)
        if r.status_code == requests.codes.ok:
            text = r.text
            return text
        else:
            logging.warning('WARNING Cannot retrieve: %s', uri)
            return None
    else:
        logging.warning('WARNING Do not recognise requests of type: %s', uri)
        return None


def yaml_at(yaml_str):
    """
    Quote escape fields with @s in Yaml
    :param yaml_str: yaml as string
    :return: yaml as string or None
    """
    at_fields = ['@value', '@id', '@context', '@type']
    if yaml_str:
        for a in at_fields:
            repl = '"' + a + '"'
            yaml_str = yaml_str.replace(a, repl)
        return yaml_str
    else:
        return None


def read_yaml(yaml_uri, clean=False):
    """
    Read YAML from a URI, and optionally clean @ fields.
    :param clean:
    :param yaml_uri: uri
    :return: python object
    """
    if yaml_uri:
        yaml_str = get_uri(yaml_uri)
        if clean:
            yaml_str = yaml_at(yaml_str)
        return yaml_str
    else:
        return None


def yaml_d(yaml_str):
    """
    Yaml to python object
    :param yaml_str: yaml as string
    :return: python obj
    """
    if yaml_str:
        d = yaml.load(yaml_str, Loader=yaml.BaseLoader)
        return d
    else:
        return None


def qname(val):
    if val:
        if ':' in val and 'http://' not in val:
            ns, value = val.split(':')
            # noinspection PyBroadException
            try:
                ns_uri = namespaces[ns]
            except:
                ns_uri = None
            if ns_uri and value:
                return ''.join([ns_uri, value])
            else:
                return None
        else:
            return None
    else:
        return None


def generate_expanded(value):
    """
    Generate an full URI for a value, if it can be identified in the namespaces.

    :param value:
    :return: uri or none
    """
    field_uri = qname(value)
    if field_uri:
        return field_uri
    else:
        return None


def template_element(dct, url, elem_t, irc_t, u_t):
    """
    Run an element dictionary through the element Jinja template to generate JSON.

    :param url: base url for the server
    :param elem_t:
    :param irc_t:
    :param u_t:
    :param dct: dictionary to process
    :return: json string from template.
    """
    with open('cs_element.jt', 'r') as f:
        t = f.read()
        if dct['crowds:uiInputOptions']:  # for drop-downs.
            dct['crowds:uiInputOptions'] = json.dumps([x.strip() for x in dct['crowds:uiInputOptions'].split(';')])
        dct['url'] = url
        dct['element_t'] = elem_t
        dct['irclass_t'] = irc_t
        dct['user'] = u_t
        template = Template(t)
        for k, v in dct.items():
            expanded = generate_expanded(value=v)
            if expanded:
                dct[k] = expanded
                label_key = k + '_label'
                dct[label_key] = v
        return template.render(sanitise_keys(dct))


def template_group(dct, url, grp_t, elem_t, irc_t, u_t, nlw_c, ida_c):
    """
    Run a group dictionary through the group Jinja template to generate JSON.

    :param elem_t:
    :param grp_t:
    :param irc_t:
    :param nlw_c:
    :param ida_c:
    :param u_t:
    :param url: base url for the server
    :param dct: dictionary to process
    :return: json string from template.
    """
    with open('cs_group.jt', 'r') as f:
        t = f.read()
        dct['url'] = url
        dct['group_t'] = grp_t
        dct['element_t'] = elem_t
        dct['irclass_t'] = irc_t
        dct['user'] = u_t
        dct['nlw_context'] = nlw_c
        dct['ida_context'] = ida_c
        template = Template(t)
        for k, v in dct.items():
            if not isinstance(v, bool):
                expanded = generate_expanded(value=v)
            else:
                expanded = None
            if expanded:
                dct[k] = expanded
                label_key = k + '_label'
                dct[label_key] = v
        return template.render(sanitise_keys(dct))  # json.loads(template.render(dct))


def sanitise_keys(d):
    """
    Strip all of the colons out of the key names
    :param d:
    :return: dict
    """
    new_d = {}
    for k, v in d.items():
        new_d[k.replace(':', '_')] = v
    return new_d


def process_group(top_level, groupss, elemss, url_b, group_t, element_t, ir_c, u):
    """
    Recursively process a capture model group.

    :param url_b: base url for the server
    :param top_level: top level group
    :param groupss: group level rows
    :param elemss: element level rows
    :param u: Omeka User ID
    :param group_t: ID for group resource template
    :param element_t: ID for element resource template.
    :param ir_c: ID for the Interactive Resource class
    :return: top_level row with parts
    """
    parts = top_level['dcterms:hasPart'].split(';')
    group_parts = [x for x in groupss if x['dcterms:identifier'] in parts]
    element_parts = [x for x in elemss if x['dcterms:identifier'] in parts]
    if group_parts:
        top_level['dcterms:hasPart'] = json.dumps(
            [json.loads(template_group(process_group(top_level=g, groupss=groupss, elemss=elemss, url_b=url_b,
                                                     group_t=group_t, element_t=element_t, ir_c=ir_c, u=u
                                                     ),
                                       url=url_b, grp_t=group_t, elem_t=element_t, irc_t=ir_c, u_t=u,
                                       ida_c=False, nlw_c=False))
             for g in group_parts])
    elif element_parts:
        top_level['dcterms:hasPart'] = json.dumps([json.loads(template_element(item, url=url_b, elem_t=element_t,
                                                                               irc_t=ir_c,
                                                                               u_t=u))
                                                   for item in element_parts])
    else:
        pass
    return top_level


def csv_load(csv_file, url_base, group, element, irclass, user, top_index='1', delimiter='|', ida_context=False):
    """
    Load a CSV file and return formatted JSON. Defaults to assuming a pipe-delimited CSV file.

    top_index sets the numbered row in the CSV (using the running_no column) to treat as the top-level group.

    N.B. does no validation of the input.

    :param ida_context:
    :param csv_file: the CSV file to open.
    :param url_base: the base for the Omeka server, e.g. 'http://nlw-omeka.digtest.co.uk'
    :param group: the Omeka ID number for the Crowd Source Group resource template
    :param element: the Omeka ID number for the Crowd Source Element resource template
    :param top_index: numbered row to treat as the top level group in the capture model
    :param user: Omeka User ID.
    :param irclass: Omeka ID for the Interactive resource class
    :param delimiter: the delimiter for the CSV, defaults to pipe '|'
    :return: json suitable for import into Omeka via the capture model importer module.
    """
    if ida_context:
        nlw_context = False
    else:
        nlw_context = True
    with open(csv_file, 'r') as csv_in:
        rows = list(csv.DictReader(csv_in, delimiter=delimiter))
        groups = [row for row in rows if row['dcterms:type'] == 'madoc:group']
        elements = [row for row in rows if row['dcterms:type'] == 'madoc:element']
        top = [t for t in groups if t['dcterms:identifier'] == top_index][0]
        group_dict = json.loads(
            template_group((process_group(top_level=top, groupss=groups, elemss=elements, url_b=url_base,
                                          group_t=group, element_t=element, ir_c=irclass, u=user)),
                           nlw_c=nlw_context, ida_c=ida_context,
                           url=url_base, grp_t=group, elem_t=element, irc_t=irclass, u_t=user))
        group_json = json.dumps(group_dict)
        group_json = group_json.replace('TRUE', 'True').replace('FALSE', 'False')  # fix case on Booleans
        return json.loads(group_json)


def csv_gen(csv_file, delimiter='|'):
    """
    Generate an empty CSV file for creating capture model.
    :param csv_file: filename to write to
    :param delimiter: delimiter for CSV, defaults to pipe '|'.
    """
    all_fields = OrderedDict([
        ('running_no', None),
        ('type', None),
        ('parts', None),
        ('title', None),
        ('label', None),
        ('description', None),
        ('conforms_to', None),
        ('input_type', None),
        ('input_options', None),
        ('input_range', None),
        ('selector_type', None),
        ('selector_value', None),
        ('purpose', None),
        ('motivation', None),
        ('body_format', None),
        ('body_type', None),
        ('required', None),
        ('derived_anno_combine', None),
        ('derived_anno_externalize', None),
        ('derived_anno_humanreadable', None),
        ('derived_anno_serialize', None),
        ('ui_choice', None),
        ('ui_multiple', None),
        ('ui_hidden', None),
        ('ui_group', None),
        ('ui_formgroup', None),
        ('body_label_parts', None),
        ('ui_component', None)

    ])
    with open(csv_file, 'w') as csv_out:
        dw = csv.DictWriter(
            csv_out, delimiter=delimiter, fieldnames=all_fields)
        dw.writeheader()


def csv_gen_vocab(csv_file, delimiter='|'):
    """
    Generate an empty CSV file for creating capture model using the Crowds RDF source. Will parse and append all of the
    vocab URIs it finds in the
    :param csv_file: filename to write to
    :param delimiter: delimiter for CSV, defaults to pipe '|'.
    """
    # dcterms_uri = 'http://dublincore.org/2012/06/14/dcterms.rdf'
    # dcterms_model = ontospy.Ontospy(dcterms_uri)
    # dcterms_properties = dcterms_model.properties
    all_fields = OrderedDict([
        ('dcterms:identifier', None),
        ('dcterms:type', None),
        ('dcterms:hasPart', None),
        ('dcterms:title', None),
        ('rdfs:label', None),
        ('dcterms:description', None),
        ('dcterms:conformsTo', None),
        ('rdfs:range', None)],
    )
    crowds = ontospy.Ontospy(
        "https://raw.githubusercontent.com/digirati-co-uk/annotation-vocab/master/crowds.rdf")
    for p in crowds.properties:
        all_fields[p.qname] = None
    with open(csv_file, 'w') as csv_out:
        dw = csv.DictWriter(
            csv_out, delimiter=delimiter, fieldnames=all_fields)
        dw.writeheader()


def main():
    """
    Initialise logging.

    Parse args.

    Write JSON.

    For example:

        python gen_json.py -i monkeys.csv -o monkeys.json -b http://www.example.com/monkeys

    Or, to generate the WW1 capture model, as JSON:

        python gen_json.py -i nlw_ww1.csv -o nlw_ww1.json -b http://nlw-omeka.digtest.co.uk -t 2

    IDA model:

        python gen_json.py -i ida_new_test.csv -o ida_new_test.json -u 2 -t 1 -c 27 -g 3 -e 1

    :return: None
    """
    logging.basicConfig(filename='capture_model.log', level=logging.DEBUG)
    parser = argparse.ArgumentParser(description='Simple CSV to JSON tool for annotation studio capture models.')
    parser.add_argument('-i', '--input', help='Input CSV file name', required=True)
    parser.add_argument('-o', '--output', help='Output JSON file name', required=True)
    parser.add_argument('-b', '--url_base', help='Base url for the Omeka instance', required=False)
    parser.add_argument('-t', '--top_index', help='Numbered element to treat as the top level group', required=False)
    parser.add_argument('-g', '--group_id', help='ID for the Crowd Source Group resource template', required=False)
    parser.add_argument('-e', '--element_id', help='ID for the Crowd Source Element resource template', required=False)
    parser.add_argument('-c', '--irclass', help='ID for the Interactive Resource class', required=False)
    parser.add_argument('-u', '--user', help='Omeka User ID for the Owner', required=False)
    parser.add_argument('-x', '--context', help='IDA Context', required=False)
    args = parser.parse_args()
    if not args.url_base:
        args.url_base = 'http://nlw-omeka.digtest.co.uk'
    if not args.irclass:
        args.irclass = 27
    if not args.group_id:
        args.group_id = 5
    if not args.element_id:
        args.element_id = 4
    if not args.user:
        args.user = 2
    if not args.context:
        args.conext = False
    if args.top_index:
        js = csv_load(csv_file=args.input, url_base=args.url_base, top_index=args.top_index, group=args.group_id,
                      element=args.element_id, irclass=args.irclass, user=args.user, ida_context=args.context)
    else:
        js = csv_load(csv_file=args.input, url_base=args.url_base, group=args.group_id,
                      element=args.element_id, irclass=args.irclass, user=args.user, ida_context=args.context)
    if js:
        with open(args.output, 'w') as o:
            json.dump(js, o, indent=4, sort_keys=True)


if __name__ == "__main__":
    main()
