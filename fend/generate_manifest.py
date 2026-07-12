import json

manifest_template = {
    "short_name": "WCE Triage UI",
    "name": "WCE Triage Kiosk user interface by React.js",
    "version": "0.3.20191107",
    "icons": [
        {
            "src": "favicon.ico",
            "sizes": "64x64 32x32 24x24 16x16",
            "type": "image/x-icon"
        }
    ],
    "start_url": ".",
    "display": "standalone",
    "theme_color": "#000000",
    "background_color": "#ffffff"
}


if __name__ == "__main__":
    with open("package.json") as package_file:
        package_data = json.load(package_file)
        manifest_template['version'] = package_data['version']

    with open("./public/manifest.json", "w") as manifest_file:
        json.dump(manifest_template, manifest_file, indent=4)
