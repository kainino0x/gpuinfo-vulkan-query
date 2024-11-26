#!/usr/bin/python3
# Format this file with python3 -m autopep8 -i fetch-new-data.py

# Run this script if you need to update the data in the data repository.
# Please be nice to the operator of the server and use the existing data to
# avoid re-scraping all of the data that's been scraped already. :)

import urllib.request
import json
import os
import re
import sys
import time


def clean_json(s):
    '''
    JSON from the gpuinfo.org API doesn't escape newlines in strings.
    Collapse whitespace into spaces to account for this.
    '''
    return re.sub(r'[\r\n\t]+ *', ' ', s)


def report_file(report_id):
    return os.path.join('data', 'reports', str(report_id) + '.json')


def exists_and_not_empty(filename):
    return os.path.exists(filename) and os.stat(filename).st_size != 0


if __name__ == '__main__':
    if not os.path.isdir(os.path.join('data', 'reports')):
        print("Run this script from outside the data repository.")
        sys.exit(1)

    with urllib.request.urlopen('https://vulkan.gpuinfo.org/api/v2/getreportlist.php') as resp:
        report_list = json.loads(clean_json(resp.read().decode('utf-8')))

    print("Found {} reports".format(len(report_list)))

    reports_to_get = []
    for report in report_list:
        report_id = int(report['url'].split('=')[1])
        if not exists_and_not_empty(report_file(report_id)):
            reports_to_get.append((report_id, report['url']))

    print("Need to get {} more reports".format(len(reports_to_get)))

    for report_id, url in reports_to_get:
        filename = report_file(report_id)
        print('Getting {}'.format(filename))

        with open(filename, 'w') as f:
            response = urllib.request.urlopen(url)
            s = response.read().decode('utf-8')
            f.write(clean_json(s))

        # Be nice to the server and don't scrape too aggressively.
        time.sleep(2.0)
