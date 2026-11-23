"""Explicit SQLite backup/restore into a NEW private file; never overwrites data."""
import argparse,sqlite3
from pathlib import Path

def snapshot(source,destination):
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Destination exists; no overwrite permitted')
    if source==destination or not source.is_file():raise ValueError('Invalid database source')
    if 'static' in destination.parts:raise ValueError('Backups must not be public')
    destination.parent.mkdir(parents=True,exist_ok=True)
    read=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    write=sqlite3.connect(destination)
    try:
        read.backup(write)
        if write.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failed')
        if write.execute('PRAGMA foreign_key_check').fetchone() is not None:raise RuntimeError('Foreign key check failed')
    finally:read.close();write.close()
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['backup','restore']);parser.add_argument('source');parser.add_argument('new_destination');args=parser.parse_args()
    # Restore deliberately creates a new checked database. Switching runtime config is a separate operator decision.
    print(snapshot(args.source,args.new_destination))
