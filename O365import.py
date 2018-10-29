from urllib.request import urlopen
import urllib
import xml.etree.ElementTree as ET
import argparse
import requests
import os
import sys
import json
import ipaddress
import platform
import configparser
import uuid

# https://endpoints.office.com/endpoints/Worldwide?clientRequestId=B66865A9-F397-4A9D-9C2B-8DEA3C46DFA7

# Service Areas
# Exchange
# Skype
# Sharepoint
# Common

urlMSBase = "https://endpoints.office.com/"
# A config file is created in a temp location to store the UUID used
if platform.system() == 'Linux':
    tmpdir = '/tmp/'
else:
    tmpdir = os.environ['TMPDIR']
workingPath = tmpdir + "/O365import-ws.ini"
config = 0
serial = 0
# This string is used as the description text for all created objects
fwdescriptiontext = "Allow without filtering all traffic for Office 365." + \
    " Generated from MS published data by script."


def eprint(*args, **kwargs):
    # Print to stderr instead of stdout

    print(*args, file=sys.stderr, **kwargs)


def getArguments():
    parser = argparse.ArgumentParser(
        description='Grab a list of video IDs from a YouTube playlist')

    parser.add_argument(
        '-f', '--firewall',
        help='To call the API directly, specify a firewall hostname or IP.' +
        'Without this, an XML API document will be output to stdout.',
        default=argparse.SUPPRESS)
    parser.add_argument(
        '-u', '--fwuser', help='Admin username for the XG firewall',
        default='admin')
    parser.add_argument(
        '-p', '--fwpassword',
        help='Password for the XG user - defaults to "admin"',
        default='password')
    parser.add_argument(
        '-a', '--add',
        help='Call API in "Add" mode - use first time only (otherwise' +
        ' Update will be used)', action='store_true')
    parser.add_argument(
        '-i', '--insecure',
        help="Don't validate the Firewall's HTTPS certificate",
        action='store_false')
    parser.add_argument(
        '-n', '--name',
        help="Define a name root for the exceptions created - default" +
        "will use 'O365 - '", default='O365 - ')
    parser.add_argument(
        '-r', '--read', metavar="filename",
        help="Read MS json from file instead of downloading it",
        default=argparse.SUPPRESS)
    parser.add_argument(
        '-o', '--optional', help="Include 'required = false' entries" +
        " from the MS list", action='store_true')
    parser.add_argument(
        '-6', '--ipv6',
        help="Include IPv6 objects & rules", action='store_true')
    parser.add_argument(
        '-s', '--securitypolicy',
        help="Create/update a firewall rule using allowing all the " +
        " created network address objects", action='store_true')
    parser.add_argument(
        '-1', '--oneshot',
        help="Create a single enormous XMLAPI transaction instead " +
        " of multiple smaller ones. Only used when outputting to stdout ",
        action='store_true')

    return parser.parse_args()


def readConfig():
    # Read in the temp config file (if it exists)
    global config
    global workingPath

    config = configparser.ConfigParser()
    config.read(workingPath)


def getserviceUUID():
    # Returns the UUID to use for calling the MS API
    # Attempts to read it from the config file. If none exists, it
    # will create a new random UUID and write it for future use.

    global serviceUUID
    global config

    if not isinstance(config, configparser.ConfigParser):
        readConfig()

    if 'DEFAULT' not in config or 'MSclientID' not in config['DEFAULT']:
        eprint("No UUID yet. Making one")
        config['DEFAULT']['MSclientID'] = str(uuid.uuid4())

    with open(workingPath, 'w') as configfile:
        config.write(configfile)

    return config['DEFAULT']['MSclientID']


def getserial():
    # Returns an incrementing serial number. Used to reference individual
    # XMLAPI transactions.
    global serial
    serial = serial + 1
    return str(serial)


def urltoregex(url):
    # Convert wildcards and periods into regex elements. Assume '*.' means
    # any subdomain, and '*' means any characters added to the given domain
    regex = '^'
    i = 0
    wildcard = 0
    for x in url:
        if x == '*':
            if i < (len(url) - 1) and url[i + 1] == '.':
                wildcard = 1
            else:
                regex = regex + '[a-zA-Z0-9.-]*'
        elif x == '.':
            if wildcard == 1:
                regex = regex + '([a-zA-Z0-9.-]*\.)?'
                wildcard = 0
            else:
                regex = regex + '\.'
        else:
            regex = regex + x
        i = i + 1

    return regex


def xgAPIStartException(name, description):
    # Returns an empty XML WebFilterException object that can be populated
    # with URLs
    exception = ET.Element('WebFilterException', transactionid=getserial())
    ET.SubElement(exception, 'Name').text = name
    ET.SubElement(exception, 'Desc').text = description
    ET.SubElement(exception, 'NewName').text = name
    ET.SubElement(exception, 'Enabled').text = "on"
    ET.SubElement(exception, 'HttpsDecrypt').text = "on"
    ET.SubElement(exception, 'VirusScan').text = "on"
    ET.SubElement(exception, 'PolicyCheck').text = "on"

    enableSrcIP = ET.SubElement(exception, 'EnableSrcIP')
    enableDstIP = ET.SubElement(exception, 'EnableDstIP')
    enableURLRegex = ET.SubElement(exception, 'EnableURLRegex')
    enableWebCat = ET.SubElement(exception, 'EnableWebCat')

    enableSrcIP.text = "no"
    enableURLRegex.text = "no"
    enableDstIP.text = "no"
    enableWebCat.text = "no"

    if type == 1:   # URLs
        enableURLRegex.text = "yes"
    elif type == 2:   # IPs
        enableSrcIP.text = "yes"

    return exception


def xgAPINewIPGroup(name, description, type):
    # Returns an empty XML IPHostGroup object.
    # Parameter 'type' must indicate IP version: 4 or 6

    if type == 4 or type == 6:
        item = ET.Element('IPHostGroup', transactionid=getserial())
        ET.SubElement(item, 'Name').text = name
        ET.SubElement(item, 'IPFamily').text = "IPv" + str(type)
        ET.SubElement(item, 'Description').text = description
        ET.SubElement(item, 'HostList')
        return item
    else:
        raise ValueError("newIPGroup must be called with type = 4 or type = 6")


def xgAPINewIPHost(name, network, group):
    # Returns an IPHost object populated with the IP address/subnet info
    # Parameter 'network' should be an IPv4Address or IPv6Address object
    # from the ipaddress module

    item = ET.Element('IPHost', transactionid=getserial())
    ET.SubElement(item, 'Name').text = name
    ET.SubElement(item, 'IPFamily').text = "IPv" + str(network.version)

    hgl = ET.SubElement(item, 'HostGroupList')
    ET.SubElement(hgl, 'HostGroup').text = group
    hosttype = ET.SubElement(item, 'HostType')

    ET.SubElement(item, 'IPAddress').text = str(network.network_address)

    if network.num_addresses == 1:
        hosttype.text = "IP"
    else:
        hosttype.text = "Network"
        # XML API needs subnet mask in dotted decimal for ipv4,
        # but in number of bits for ipv6
        if network.version == 4:
            ET.SubElement(item, 'Subnet').text = str(network.netmask)
        elif network.version == 6:
            ET.SubElement(item, 'Subnet').text = str(network.prefixlen)

    return item


def xgAPILogin(fwuser, fwpassword):
    # Returns a root Login element for an XMLAPI call

    requestroot = ET.Element('Request')
    login = ET.SubElement(requestroot, 'Login')
    ET.SubElement(login, 'Username').text = fwuser
#  ET.SubElement(login, 'Password', passwordform = 'encrypt').text = fwpassword
    ET.SubElement(login, 'Password').text = fwpassword

    return requestroot


def xgAPIStartFWRule(version):
    # Returns an XMLAPI SecurityPolicy object representing a firewall rule with
    # an empty destination list
    # Parameter version specifies the IP protocol version : 4 or 6

    rule = ET.Element('SecurityPolicy', transactionid=getserial())
    ET.SubElement(
        rule, 'Name').text = "Office 365 bypass rule IPv" + str(version)
    ET.SubElement(rule, 'Description').text = fwdescriptiontext
    if version == 4:
        ET.SubElement(rule, 'IPFamily').text = "IPv4"
    elif version == 6:
        ET.SubElement(rule, 'IPFamily').text = "IPv6"
    else:
        raise ValueError(
            'Unrecognised IP version number passed to startFWRule')

    ET.SubElement(rule, 'PolicyType').text = "Network"
    ET.SubElement(rule, 'Status').text = "Disable"
    ET.SubElement(rule, 'Position').text = "Top"

    zones = ET.SubElement(rule, 'SourceZones')
    ET.SubElement(zones, 'Zone').text = "LAN"
    ET.SubElement(zones, 'Zone').text = "WiFi"
    ET.SubElement(zones, 'Zone').text = "DMZ"

    dzones = ET.SubElement(rule, 'DestinationZones')
    ET.SubElement(dzones, 'Zone').text = "WAN"

    services = ET.SubElement(rule, 'Services')
    ET.SubElement(services, 'Service').text = "HTTP"
    ET.SubElement(services, 'Service').text = "HTTPS"

    ET.SubElement(rule, 'Schedule').text = "All The Time"
    ET.SubElement(rule, 'Action').text = "Accept"
    ET.SubElement(rule, 'LogTraffic').text = "Enable"
    ET.SubElement(rule, 'MatchIdentity').text = "Disable"
    ET.SubElement(rule, 'DSCPMarking').text = "-1"
    ET.SubElement(rule, 'ApplicationControl').text = "None"
    ET.SubElement(rule, 'ApplicationBaseQoSPolicy').text = "Revoke"
    ET.SubElement(rule, 'WebFilter').text = "None"
    ET.SubElement(rule, 'WebFilterBaseQoSPolicy').text = "Revoke"
    ET.SubElement(rule, 'IntrusionPrevention').text = "None"
    ET.SubElement(rule, 'TrafficShappingPolicy').text = "None"
    ET.SubElement(rule, 'ApplyNAT').text = "CustomNatPolicy"
    ET.SubElement(rule, 'OverrideGatewayDefaultNATPolicy').text = "Disable"
    ET.SubElement(rule, 'OutboundAddress').text = "MASQ"
    ET.SubElement(rule, 'PrimaryGateway')
    ET.SubElement(rule, 'BackupGateway')
    ET.SubElement(rule, 'ScanHTTP').text = "Disable"
    ET.SubElement(rule, 'ScanHTTPS').text = "Disable"
    ET.SubElement(rule, 'Sandstorm').text = "Disable"
    ET.SubElement(rule, 'BlockQuickQuic').text = "Disable"
    ET.SubElement(rule, 'ScanFTP').text = "Disable"
    ET.SubElement(rule, 'SourceSecurityHeartbeat').text = "Disable"
    ET.SubElement(rule, 'MinimumSourceHBPermitted').text = "No Restriction"
    ET.SubElement(rule, 'DestSecurityHeartbeat').text = "Disable"
    ET.SubElement(
        rule, 'MinimumDestinationHBPermitted').text = "No Restriction"
    ET.SubElement(rule, 'DestinationNetworks')

    return rule


def xgAPIGetDestNets(fwrule):
    # Returns the DestinationNetworks element from a given firewall rule
    # Parameter fwrule contains the XML API firewall rule object to search

    return fwrule.find('DestinationNetworks')


def xgAPIPost(requestroot):
    # Posts an XMLAPI document to the firewall specified in command line -f arg
    # If there is no -f arg, it prints the document to stdout
    # Parameter 'requestroot' provides the root element of the XML document

    postdata = {
        'reqxml': ET.tostring(requestroot, 'unicode')
    }

    try:
        callurl = 'https://' + stuff.firewall + \
            ':4444/webconsole/APIController'
        r = requests.post(callurl, data=postdata, verify=stuff.insecure)
        eprint(r)
        eprint(r.text)
    except AttributeError:
        print(ET.tostring(requestroot, 'unicode'))


def callMSAPI(method, instance, clientId):
    # Makes a call to the Microsoft Web Service to get the Endpoint data
    # If successful, returns a json object built from the downloaded data

    reqPath = urlMSBase + "/" + method + "/" + \
        instance + "?clientRequestId=" + clientId
    eprint("Calling MS API:" + reqPath)
    request = urllib.request.Request(reqPath)
    try:
        with urlopen(request) as response:
            rawresponse = response.read().decode()
            return json.loads(rawresponse)
    except urllib.error.HTTPError as e:
        eprint('HTTPError = ' + str(e.code))
    except urllib.error.URLError as e:
        eprint('URLError = ' + str(e.reason))
        raise SystemExit()
    except Exception:
        import traceback
        eprint('generic exception: ' + traceback.format_exc())


def isRequired(required):
    # Returns a string to include in the object name depending on whether
    # MS specifies it's a required bypass or not

    if required:
        return "Required"
    else:
        return "Not Required"


def shouldIInclude(epGroup):
    # Checks to see if a given group in the MS endpoint data should be
    # included in the XML API call
    # Returns True or False accordingly

    # Only include groups from the 'Optimize' or 'Allow' category
    if epGroup['category'] not in ('Optimize', 'Allow'):
        return False

    # Only include groups that are marked 'required' unless the -o
    # command line flag is set
    if not (epGroup['required'] or stuff.optional):
        return False

    # Only include groups relating to tcp ports 443 or 80
    ports = str(epGroup['tcpPorts'])
    if (ports.find('443') < 0 and ports.find('80') < 0):
        return False

    return True


# Fun starts here

# Check command line
stuff = getArguments()

# Get the source json from website or local file
endpointGroups = callMSAPI('endpoints', 'Worldwide', getserviceUUID())

# If there's a firewall address set, make sure we're in oneshot mode
try:
    eprint("Config will be posted to " + stuff.firewall)
    stuff.oneshot = False
except AttributeError:
    eprint("No firewall set")

if stuff.add:
    method = 'add'
else:
    method = 'update'

# Start building the XMLAPI Request
fwRequestroot = xgAPILogin(stuff.fwuser, stuff.fwpassword)

fwRequestSet = ET.SubElement(fwRequestroot, 'Set', operation=method)
fwrule4 = xgAPIStartFWRule(4)
destnets4 = xgAPIGetDestNets(fwrule4)
fwrule6 = xgAPIStartFWRule(6)
destnets6 = xgAPIGetDestNets(fwrule6)

# Iterate through the 'Product' entries in the source XML looking for URL
# definitions.
# First collect all URLs and make them into Web Exceptions
for epGroup in endpointGroups:
    if shouldIInclude(epGroup):
        if stuff.oneshot:
            thisRequest = fwRequestroot
            outroot = fwRequestSet
        else:
            thisRequest = xgAPILogin(stuff.fwuser, stuff.fwpassword)
            outroot = ET.SubElement(thisRequest, 'Set', operation=method)

        txtDescRoot = "ID: " + \
            str(epGroup['id']) + ' - ' + epGroup['serviceAreaDisplayName'] + \
            ' (' + isRequired(epGroup['required']) + ')'
        if 'notes' in epGroup:
            txtDescRoot = txtDescRoot + '\n' + epGroup['notes']

        txtGroupName = str(epGroup['id']) + ' (' + epGroup['serviceArea'] + ')'

        if 'urls' in epGroup:
            newList = xgAPIStartException(
                stuff.name + txtGroupName, txtDescRoot)
            dlist = ET.SubElement(newList, 'DomainList')
            for url in epGroup['urls']:
                ET.SubElement(dlist, 'URLRegex').text = urltoregex(url)
            outroot.append(newList)

        if 'ips' in epGroup:
            # It's an IP list, so create a new IP Group and add the
            # hosts/networks to it
            group4name = ""
            group6name = ""

            count = 0
            for ip in epGroup['ips']:

                network = ipaddress.ip_network(ip)
                if network.version == 4:
                    if group4name == "":
                        group4name = stuff.name + "IPv4 - " + txtGroupName
                        outroot.append(xgAPINewIPGroup(
                            group4name, txtDescRoot, 4))
                    groupname = group4name
                elif network.version == 6:
                    if group6name == "":
                        group6name = stuff.name + "IPv6 - " + txtGroupName
                        outroot.append(xgAPINewIPGroup(
                            group6name, txtDescRoot, 6))
                    groupname = group6name
                outroot.append(xgAPINewIPHost(
                    groupname + " - " + str(count), network, groupname))
                count = count + 1

# Add groups to the relevant firewall rules
            if count > 0:
                if group4name != "":
                    ET.SubElement(destnets4, 'Network').text = group4name
                if group6name != "":
                    ET.SubElement(destnets6, 'Network').text = group6name

        if not stuff.oneshot:
            eprint("Posting " + txtGroupName)
            xgAPIPost(thisRequest)

# Now we've finished building all the objects, add the completed firewall
# rules to the end of the document
if stuff.securitypolicy:
    fwRequestSet.append(fwrule4)
    fwRequestSet.append(fwrule6)
    if not stuff.oneshot:
        eprint("Posting firewall rules")
    xgAPIPost(fwRequestroot)


# Take the xml output from this program and send it to your firewall with curl,
# for example:
#   $ curl -k https://<firewall ip>:4444/webconsole/APIController -F "reqxml=<foo.xml"
