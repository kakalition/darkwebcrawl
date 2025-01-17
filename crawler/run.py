import argparse
import importlib
import logging
import os
import sys
import traceback

from config import SITES, PROFILES, LINKS

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s"
)

def run_site(site_name, urls, idpost=None):
    try:
        dir_path = os.path.dirname(os.path.realpath(__file__))
        src_path = os.path.join(dir_path, "src")
        sys.path.append(src_path)
        
        module = importlib.import_module(site_name)
        crawler_class = getattr(module, "DarkwebCrawler")
        
        crawler_instance = crawler_class()
        for url in urls:
            # Pastikan idpost dikirim jika diperlukan
            if idpost is not None:
                crawler_instance.run(url, idpost)
            else:
                crawler_instance.run(url)
    
    except ModuleNotFoundError:
        logging.error(f"Module {site_name} not found.")
    except AttributeError:
        logging.error(f"run_site {traceback.format_exc()}")
        logging.error(f"DarkwebCrawler class not found in {site_name} module.")
    except TypeError as e:
        logging.error(f"TypeError: {e}")

def main():
    parser = argparse.ArgumentParser(description="Web crawler for various sites.")
    parser.add_argument(
        "--sites",
        help="Names of the sites to crawl, \
            separated by comma. If not specified, all sites will be crawled.",
    )
    parser.add_argument(
        "--profiles",
        help="Account profiles of the sites to crawl, \
            separated by comma. If not specified, all profiles will be crawled.",
    )
    parser.add_argument(
        "--links",
        help="Links names to crawl, \
            separated by comma. If not specified, all links will be crawled.",
    )
    
    args = parser.parse_args()
    
    selected_sites = args.sites.split(",") if args.sites else []
    selected_profiles = args.profiles.split(",") if args.profiles else []
    selected_links = args.links.split(",") if args.links else []
    
    available_sites = [site["name"] for site in SITES]
    available_profiles = [profile["name"] for profile in PROFILES]
    available_links = [link["name"] for link in LINKS]
    
    invalid_sites = [site for site in selected_sites if site not in available_sites]
    invalid_profiles = [profile for profile in selected_profiles 
                        if profile not in available_profiles]
    invalid_links = [link for link in selected_links 
                     if link not in available_links]
    
    if invalid_sites:
        logging.error(f"Invalid site names provided: {', '.join(invalid_sites)}")
        return
    
    if invalid_profiles:
        logging.error(f"Invalid profile names provided: {', '.join(invalid_profiles)}")
        return
    
    if invalid_links:
        logging.error(f"Invalid link names provided: {', '.join(invalid_links)}")
        return
    
    if selected_sites:
        for site in SITES:
            if site["name"] in selected_sites:
                logging.info(f"Running {site['name']}")
                run_site(site["name"], site["urls"], site.get("idpost"))
    
    if selected_profiles:
        for profile in PROFILES:
            if profile["name"] in selected_profiles:
                logging.info(f"Running {profile['name']}")
                run_site(profile["name"], profile["profile_urls"], profile.get("idpost"))
    
    if selected_links:
        for link in LINKS:
            if link["name"] in selected_links:
                logging.info(f"Running {link['name']}")
                run_site(link["name"], link["link_urls"], link.get("idpost"))
    
    # If no specific arguments are provided, run everything
    if not (selected_sites or selected_profiles or selected_links):
        logging.info("Running all sites, profiles, and links")
        
        for site in SITES:
            logging.info(f"Running {site['name']}")
            run_site(site["name"], site["urls"], site.get("idpost"))
        
        for profile in PROFILES:
            logging.info(f"Running {profile['name']}")
            run_site(profile["name"], profile["profile_urls"], profile.get("idpost"))
        
        for link in LINKS:
            logging.info(f"Running {link['name']}")
            run_site(link["name"], link["link_urls"], link.get("idpost"))

if __name__ == "__main__":
    main()
