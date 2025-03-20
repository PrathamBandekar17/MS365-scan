import os
import json
import requests
from flask import Flask, jsonify, request, redirect, session
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY") 

# Microsoft OAuth settings
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
AUTHORITY = "https://login.microsoftonline.com/common/oauth2/v2.0"
SCOPES = ["Files.Read.All", "Sites.Read.All"]

# Microsoft Graph API endpoints
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"

def get_access_token(code):
    """ Exchange authorization code for access token """
    token_url = f"{AUTHORITY}/token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
        "scope": " ".join(SCOPES),
    }
    response = requests.post(token_url, data=data)
    return response.json()

@app.route("/login")
def login():
    """ Redirect user to Microsoft's OAuth login page """
    auth_url = f"{AUTHORITY}/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={' '.join(SCOPES)}&response_mode=query"
    return redirect(auth_url)

@app.route("/callback")
def callback():
    """ Handle OAuth callback and get access token """
    code = request.args.get("code")
    token_data = get_access_token(code)
    session["access_token"] = token_data.get("access_token")
    return redirect("/scan")

def get_files_from_drive(drive_url, access_token):
    """ Fetch files from OneDrive or SharePoint """
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(drive_url, headers=headers)
    if response.status_code == 200:
        return response.json().get("value", [])
    return []

@app.route("/scan", methods=["GET"])
def scan():
    """ Scan OneDrive and SharePoint files """
    access_token = session.get("access_token")
    if not access_token:
        return redirect("/login")
    
    # Fetch OneDrive files
    one_drive_files = get_files_from_drive(f"{GRAPH_API_BASE_URL}/me/drive/root/children", access_token)
    
    # Fetch SharePoint sites 
    sharepoint_sites = get_files_from_drive(f"{GRAPH_API_BASE_URL}/sites/root/drive/root/children", access_token)
    
    files_data = {
        "OneDrive": one_drive_files,
        "SharePoint": sharepoint_sites
    }
    
    with open("ms365_scan_report.json", "w") as f:
        json.dump(files_data, f, indent=4)
    
    return jsonify(files_data)

@app.route("/search", methods=["GET"])
def search():
    """ Search for specific files in OneDrive and SharePoint """
    search_term = request.args.get("term", "").strip()
    if not search_term:
        return jsonify({"error": "Search term is required"}), 400
    
    try:
        with open("ms365_scan_report.json", "r") as f:
            files_data = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "Scan report not found. Please scan first."}), 400
    
    def filter_files(files):
        return [file for file in files if search_term.lower() in file.get("name", "").lower()]
    
    results = {
        "OneDrive": filter_files(files_data.get("OneDrive", [])),
        "SharePoint": filter_files(files_data.get("SharePoint", []))
    }
    
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)