import re
import json
import logging
import requests
import argparse
from thefuzz import fuzz
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text


def extract_text_from_pdf(pdf_path):
    try:
        return extract_text(pdf_path)
    except Exception as e:
        return str(e)


def extract_dmp_id(text):
    match = re.search(r'DMP ID:\s+(https?://doi\.org/[^\s]+)', text)
    return match.group(1).strip() if match else None


def extract_creator(text):
    match = re.search(r'Creator:\s+([^\n]+)', text)
    return match.group(1).strip() if match else None


def is_orcid_present(creator):
    return "ORCID" in creator


def extract_affiliation(text):
    match = re.search(r'Affiliation:\s+([^\(]+)', text)
    return match.group(1).strip() if match else None


def search_orcid(creator_name, affiliation):
    print(creator_name, affiliation)
    orcid_api_url = "https://pub.orcid.org/v3.0/search/"
    headers = {"Accept": "application/json"}
    params = {
        "q": f'name:"{creator_name}" AND employment-org-name:"{affiliation}"'
    }
    try:
        response = requests.get(orcid_api_url, headers=headers, params=params)
        print(response.url)
        if response.status_code == 200:
            data = response.json()
            return [result["orcid-identifier"]["path"] for result in data["result"]]
        else:
            logging.error(f'Error searching ORCID for: {creator_name} - Status Code: {response.status_code}, Response: {response.text}')
            return []
    except Exception as e:
        logging.error(f'Exception while searching ORCID for: {creator_name} - {e}')
        return []


def search_orcid(creator_name, affiliation):
    try:
        base_url = "https://pub.orcid.org/v3.0/expanded-search/"
        params = {
            "q": f'given-and-family-names:"{creator_name}" AND affiliation-org-name:"{affiliation}"',
            "fl": "orcid,given-names,family-name,current-institution-affiliation-name,past-institution-affiliation-name"
        }
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'xml')
            expanded_search = soup.find('expanded-search:expanded-search')
            if expanded_search and expanded_search['num-found'] != '0':
                orcid_urls = []
                orcid_id_tags = soup.find_all('expanded-search:orcid-id')
                for tag in orcid_id_tags:
                    orcid_id = tag.text.strip()
                    orcid_url = f"https://orcid.org/{orcid_id}"
                    orcid_urls.append(orcid_url)
                return orcid_urls
            else:
                return None
        else:
            logging.error(f'Error searching ORCID for: {creator_name} - Status Code: {response.status_code}, Response: {response.text}')
            return None
    except Exception as e:
        logging.error(f'Exception while searching ORCID for: {creator_name} - {e}')
        return None


def extract_funder(text):
    match = re.search(r'Funder:\s+([^\(]+)', text)
    return match.group(1).strip() if match else None


def extract_funding_opportunity_number(text):
    match = re.search(r'Funding opportunity number:\s+([^\n]+)', text)
    return match.group(1).strip() if match else None


def search_ror(organization_name):
    chosen_result = None
    try:
        url = "https://api.ror.org/organizations"
        params = {"affiliation": organization_name}
        r = requests.get(url, params=params)
        api_response = r.json()
        results = api_response['items']
        if results:
            for result in results:
                if 'chosen' in result and result['chosen']:
                    chosen_result = result['organization']['id']
                    break
    except Exception as e:
        logging.error(f'Error for query: {organization_name} - {e}')
    return chosen_result


def search_ror_for_funder(funder_name):
    chosen_id, preferred_funder_id = None, None
    url = "https://api.ror.org/organizations"
    params = {"affiliation": funder_name}
    r = requests.get(url, params=params)
    api_response = r.json()
    results = api_response.get('items', [])
    for result in results:
        if result.get('chosen'):
            record = result.get('organization', {})
            chosen_id = record['id']
            fundref_details = record.get('external_ids', {}).get('FundRef', {})
            preferred_funder_id = fundref_details.get('preferred')
            if not preferred_funder_id and len(fundref_details.get('all', [])) == 1:
                preferred_funder_id = fundref_details['all'][0]
            break
    return chosen_id, preferred_funder_id


def normalize_text(text):
    return text.lower().strip()


def search_funder_registry(org_name):
    url = 'https://api.crossref.org/funders'
    params = {'query': org_name}
    api_response = requests.get(url, params=params).json()
    for item in api_response['message']['items']:
        match_ratio = fuzz.token_set_ratio(
            org_name, normalize_text(item['name']))
        if match_ratio > 90:
            return item['id']
        elif org_name in item['alt-names']:
            return item['id']
    else:
        return None


def get_award_works(award_number):
    crossref_api_url = f"https://api.crossref.org/works?filter=award.number:{award_number}"
    try:
        response = requests.get(crossref_api_url)
        if response.status_code == 200:
            data = response.json()
            results = {'dois': [], 'funder_ids': []}
            for item in data['message']['items']:
                results['dois'].append(item['DOI'])
                for funder in item.get('funder', []):
                    results['funder_ids'].append(funder['DOI'])
            return results
    except Exception as e:
        return {}


def compile_results_to_json(dmp_id, orcid_results, creator, affiliation, ror_id_affiliation, funder_name, funder_id, ror_id_funder, funder_id_from_ror, funding_opportunity_number, crossref_info):
    results = {
        "inputs": {
            "dmp_id": dmp_id,
            "affiliation": affiliation,
            "funder_name": funder_name,
            "funding_opportunity_number": funding_opportunity_number
        },
        "matches": {
            "dmp_id": {
                "input": dmp_id
            },
            "creator_orcid": {
                "input": [creator, affiliation],
                "orcid": orcid_results
            },
            "affiliation": {
                "input": affiliation,
                "ror_id": ror_id_affiliation
            },
            "funder_name": {
                "input": funder_name,
                "funder_id": funder_id,
                "ror_id": ror_id_funder,
                "funder_id_from_ror": funder_id_from_ror
            },
            "funding_opportunity_number": {
                "input": funding_opportunity_number,
                "crossref_award_works": crossref_info
            }
        }
    }
    return json.dumps(results, indent=2)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='"Pidify" a PDF output by DMPTool')
    parser.add_argument('-i', '--input_pdf',
                        help='Input PDF file', required=True)
    return parser.parse_args()


def main():
    args = parse_arguments()
    extracted_text = extract_text_from_pdf(args.input_pdf)
    dmp_id = extract_dmp_id(extracted_text)
    creator = extract_creator(extracted_text)
    affiliation = extract_affiliation(extracted_text)
    funder_name = extract_funder(extracted_text)
    funding_opportunity_number = extract_funding_opportunity_number(
        extracted_text)
    orcid_results = None
    if not is_orcid_present(creator):
        orcid_results = search_orcid(creator, affiliation)
    ror_id_affiliation = search_ror(affiliation)
    ror_id_funder, funder_id_from_ror = search_ror_for_funder(funder_name)
    funder_id = search_funder_registry(funder_name)
    crossref_info = get_award_works(funding_opportunity_number)
    json_result = compile_results_to_json(
        dmp_id, orcid_results, creator, affiliation, ror_id_affiliation, funder_name, funder_id, ror_id_funder, funder_id_from_ror, funding_opportunity_number, crossref_info)
    print(json_result)


if __name__ == "__main__":
    main()
