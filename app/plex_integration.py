"""
Plex integration module for Bozloader.
Handles triggering library scans after file approval.
"""

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from config import Config


def get_library_section_id(library_name: str) -> str:
    """Get the Plex library section ID by name."""
    if not Config.PLEX_ENABLED:
        return None
    
    url = f"{Config.PLEX_URL}/library/sections?X-Plex-Token={Config.PLEX_TOKEN}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            root = ET.fromstring(data)
            
            for directory in root.findall('.//Directory'):
                if directory.get('title') == library_name:
                    return directory.get('key')
            
            print(f"Library '{library_name}' not found in Plex")
            return None
            
    except urllib.error.HTTPError as e:
        print(f"Failed to get Plex libraries: {e}")
        return None
    except Exception as e:
        print(f"Error getting Plex libraries: {e}")
        return None


def trigger_plex_scan(library_name: str) -> bool:
    """Trigger a Plex library scan."""
    if not Config.PLEX_ENABLED:
        print("Plex integration not configured - skipping scan")
        return False
    
    section_id = get_library_section_id(library_name)
    
    if not section_id:
        print(f"Could not find library section for '{library_name}'")
        return False
    
    url = f"{Config.PLEX_URL}/library/sections/{section_id}/refresh?X-Plex-Token={Config.PLEX_TOKEN}"
    
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=10) as response:
            print(f"Plex library scan triggered for '{library_name}' (section {section_id})")
            return True
            
    except urllib.error.HTTPError as e:
        print(f"Failed to trigger Plex scan: {e}")
        return False
    except Exception as e:
        print(f"Error triggering Plex scan: {e}")
        return False


def test_plex_connection() -> dict:
    """Test Plex server connection and return server info."""
    if not Config.PLEX_ENABLED:
        return {"status": "disabled", "message": "Plex integration not configured"}
    
    url = f"{Config.PLEX_URL}?X-Plex-Token={Config.PLEX_TOKEN}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            root = ET.fromstring(data)
            
            return {
                "status": "connected",
                "server_name": root.get('friendlyName', 'Unknown'),
                "version": root.get('version', 'Unknown'),
                "platform": root.get('platform', 'Unknown')
            }
            
    except urllib.error.HTTPError as e:
        return {"status": "error", "message": f"HTTP Error: {e.code}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_libraries() -> list:
    """Get list of all Plex libraries."""
    if not Config.PLEX_ENABLED:
        return []
    
    url = f"{Config.PLEX_URL}/library/sections?X-Plex-Token={Config.PLEX_TOKEN}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()
            root = ET.fromstring(data)
            
            libraries = []
            for directory in root.findall('.//Directory'):
                libraries.append({
                    "key": directory.get('key'),
                    "title": directory.get('title'),
                    "type": directory.get('type')
                })
            
            return libraries
            
    except Exception as e:
        print(f"Error getting Plex libraries: {e}")
        return []
