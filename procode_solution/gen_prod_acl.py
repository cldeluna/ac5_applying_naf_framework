#!/usr/bin/python -tt
# Project: acl_automated_workflow
# Filename: gen_prod_acl.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "3/24/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import jinja2
import yaml
import os

import utilities

def generate_acl(use_infrahub: bool = False, fallback_on_error: bool = True):
    """
    Generate ACL configuration from template.
    
    Args:
        use_infrahub: Whether to fetch IPs from InfraHub (with fallback to local file on error)
        fallback_on_error: If True, falls back to local file when InfraHub fails
        
    Returns:
        tuple: (dns_ips, rendered_acl, source, error_msg)
            - dns_ips: List of IP addresses used
            - rendered_acl: The generated ACL configuration
            - source: String describing the source ("InfraHub", "local file", or "local file (fallback)")
            - error_msg: Error message if generation failed, None otherwise
    """
    dns_ips = None
    source = None
    error_msg = None
    
    # Try InfraHub first if requested
    if use_infrahub:
        dns_ips, error_msg = utilities.get_prod_dhcp_ips()
        if dns_ips:
            source = "InfraHub"
        elif dns_ips == [] and not error_msg:
            # InfraHub returned empty list (API succeeded but no IPs found)
            error_msg = "InfraHub returned 0 IP addresses"
            if fallback_on_error:
                pass  # Will fall through to local file below
            else:
                return None, None, None, error_msg
        elif fallback_on_error:
            # InfraHub failed - try local file as fallback
            pass  # Will fall through to local file below
        else:
            return None, None, None, error_msg or "Failed to retrieve IPs from InfraHub"
    
    # Use local file if InfraHub not requested OR if InfraHub failed with fallback enabled
    if not dns_ips:
        try:
            with open('prod_dhcp_ips.yml', 'r') as f:
                data = yaml.safe_load(f)
                dns_ips = data['dns_ips']
            source = "local file" if not use_infrahub else "local file (fallback)"
        except Exception as e:
            return None, None, None, f"Error loading from local file: {str(e)}"
    
    if not dns_ips:
        return None, None, None, "No IPs available from any source"
    
    # Load template and render ACL
    try:
        template_dir = './templates'
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))
        template = env.get_template('production_acl.j2')
        rendered_acl = template.render(dns_ips=dns_ips)
        
        # Save to output directory
        output_dir = './output'
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'production_acl.txt')
        with open(output_file, 'w') as f:
            f.write(rendered_acl)
        
        return dns_ips, rendered_acl, source, error_msg
        
    except Exception as e:
        return None, None, None, f"Error generating ACL: {str(e)}"


def main(args):
    """Main entry point for command-line usage."""
    dns_ips, rendered_acl, source, error_msg = generate_acl(
        use_infrahub=args.infrahub, 
        fallback_on_error=True  # Fallback to local file on InfraHub errors
    )
    
    if error_msg and not dns_ips:
        # Only error out if we couldn't get IPs from any source
        print(f"Error: {error_msg}")
        return 1
    
    # Show warning if InfraHub failed but we fell back to local file
    if error_msg and "fallback" in str(source):
        print(f"Warning: {error_msg}")
        print("Fell back to local file (prod_dhcp_ips.yml)")
        print()
    
    print(f"Source: {source}")
    print(f"IPs used: {dns_ips}")
    print(f"Generated config saved to: ./output/production_acl.txt")
    print("\n--- Generated ACL ---\n")
    print(rendered_acl)
    return 0


# Standard call to the main() function.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generate production ACL configuration",
                                     epilog="Usage: python gen_prod_acl.py [-i]")

    parser.add_argument('-i', '--infrahub', help='Get Production IPs from InfraHub', 
                        action='store_true', default=False)
    arguments = parser.parse_args()
    exit_code = main(arguments)
    exit(exit_code)
 