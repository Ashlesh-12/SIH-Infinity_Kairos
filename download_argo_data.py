import ftplib
import os
import sys

def download_directory_recursive(ftp, remote_dir, local_dir):
    """
    Recursively downloads a directory from an FTP server,
    skipping files that have already been downloaded.
    """
    print(f"Entering remote directory: {remote_dir}")
    try:
        ftp.cwd(remote_dir)
        
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)
        
        dir_listing = []
        ftp.dir('.', dir_listing.append)
        
        for item in dir_listing:
            parts = item.split()
            name = parts[-1]
            
            if item.startswith('d'):  # It's a directory
                download_directory_recursive(ftp, name, os.path.join(local_dir, name))
                ftp.cwd('..')
            else:  # It's a file
                local_filepath = os.path.join(local_dir, name)
                
                # Add this check
                if name.endswith('.nc') and not os.path.exists(local_filepath):
                    print(f"Downloading file: {name} to {local_filepath}")
                    with open(local_filepath, 'wb') as local_file:
                        ftp.retrbinary('RETR ' + name, local_file.write)
                else:
                    print(f"Skipping {name} (already exists or not a NetCDF file).")

    except ftplib.all_errors as e:
        print(f"FTP error: {e}", file=sys.stderr)

def main():
    ftp_host = 'ftp.ifremer.fr'
    ftp_path_root = '/ifremer/argo/dac/incois/'
    local_download_dir = 'argo_data'
    
    print(f"Connecting to FTP server: {ftp_host}")
    try:
        with ftplib.FTP(ftp_host) as ftp:
            ftp.login()
            print("Connected and logged in.")
            
            download_directory_recursive(ftp, ftp_path_root, local_download_dir)
            
    except ftplib.all_errors as e:
        print(f"Could not connect to FTP server: {e}", file=sys.stderr)
        
if __name__ == "__main__":
    main()