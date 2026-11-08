"""Offline restore to a new path. Never overwrites the running database."""
import argparse,json
from quotepilot.backups import restore

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('backup');parser.add_argument('new_database')
    parser.add_argument('--sha256',required=True)
    args=parser.parse_args()
    print(json.dumps(restore(args.backup,args.new_database,args.sha256),ensure_ascii=False,indent=2))
