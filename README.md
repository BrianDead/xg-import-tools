# xg-import-tools
Some **unofficial** tools to help import config into a Sophos XG Firewall

# O365import.py
Fetches Microsoft Office365 Endpoint data from their web service API and uses it to create objects and definitions on an XG firewall to skip filtering/scanning for the traffic.

It requires Python 3.

If you run it in without any command-line parameters , it will output to stdout a set of XMLAPI transactions for each of the product groupings in the Microsoft data. It will create Web Exceptions for all the URLs and it will create IPHost or IP Network objects and Network Groups for all the IP Address specifications.

Command-line parameters: 
* ‘-a’ creates the XML API calls in ‘add’ mode, to be used the first time you create the objects. Subsequent calls without ‘-a’ will update the objects, so the script can be run regularly to keep up to date with changes to Microsoft’s list
* ‘-1’ will output these as one single enormous XMLAPI transaction.
* ‘-s’ will include two firewall rule entries as well – one for all the IPv4 groups and one for all the IPv6 groups created.
* ‘-u’, ‘-p’ allow you to set the username and password to be used for the XMLAPI calls
* ‘-f `<address>`’ will make it actually call the firewall at the specified address and post directly to the XML API service
   You will need to configure the firewall to allow XMLAPI connections from the machine you’re running the script on
* ‘-i' when calling the firewall’s XMLAPI, ignore certificate validation errors

When you use the -f mode to call the API, the requests are broken up into multiple transactions. The XML response for each is displayed without interpretation. Check the status codes - anything other than 
	`<Status code="200">Configuration applied successfully.</Status>`
suggests an entry didn’t work correctly.

## Examples

`python3 O365import.py -a -i -f 172.16.16.16 -u admin -p sophos`

This will fetch the Microsoft data, then attempt to post it as 'add' operations to an XG Firewall at 172.16.16.16. It will use the username 'admin' and the password 'sophos'

`python3 O365import.py -1 -u admin -p sophos > xaction.xml`

This will fetch the MS data, build a single large XMLAPI transaction and write it to xaction.xml. You could then use curl to post the XML document to the API. Note that this can be very large and take tens of minutes before you see any feedback.
