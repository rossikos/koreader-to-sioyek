#!/usr/bin/env python3
import sys
import os
import sqlite3
from sioyek.sioyek import Sioyek, Highlight, clean_path, DocumentPos
import hashlib
import re
import ast
import uuid

LOCAL_DATABASE_FILE = ""
SHARED_DATABASE_FILE = ""
SIOYEK_PATH = ""
KOREADER_DIRECTORY = ""

def get_md5_hash(path):
    m = hashlib.md5()
    with open(path, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()

def get_partial_md5_hash(path):
    m = hashlib.md5()
    step, size = 1024, 1024

    with open(path, "rb") as file_:
        sample = file_.read(size)
        if sample:
            m.update(sample)
        for i in range(11):
            file_.seek((4 ** i) * step)
            sample = file_.read(size)
            if sample:
                m.update(sample)
            else:
                break
    return m.hexdigest()

def scan_dir(path):
    if not os.path.isdir(path):
        print("provide the path to a valid directory containing PDFs and their respective 'metadata.pdf.lua' files")
        sys.exit()

    pdffiles = []
    pdfhashes = []
    pdf_partial_hashes = []

    datafiles = []
    datadicts = []

    for subdir, dirs, files in os.walk(path):
        pdffiles.extend([os.path.join(subdir, f) for f in files if f.endswith('.pdf')])
        datafiles.extend([os.path.join(subdir, f) for f in files if f == 'metadata.pdf.lua'])

    for i in pdffiles:
        pdfhashes.append(get_md5_hash(i))
        pdf_partial_hashes.append(get_partial_md5_hash(i))

    for i in datafiles:
        with open(i, encoding='utf-8') as f:
            content = f.read()
            content = re.sub(r'^-- .*\n', '', content)
            content = re.sub(r'^return ', '', content)
            content = re.sub(r'\["(\w*)"\] =', r'"\1":', content)
            content = re.sub(r'\[([\d\d?]*)\] =', r'"\1":', content)
            content = re.sub(r'": false,', '": False,', content)
            content = re.sub(r'": true,', '": True,', content)
        datadicts.append(ast.literal_eval(content))

    hash_data = []
    for idi, i in enumerate(pdf_partial_hashes):
        for j in datadicts:
            if i == j['partial_md5_checksum']:
                hash_data.append((pdfhashes[idi], j, pdffiles[idi]))
                # hash_data.append((pdfhashes[idi], j))
    
    return hash_data

def main():
    if len(sys.argv) < 2:
        if KOREADER_DIRECTORY:
            hash_data = scan_dir(KOREADER_DIRECTORY)
    else:
        hash_data = scan_dir(sys.argv[1])
        
    sioyek = Sioyek(SIOYEK_PATH, LOCAL_DATABASE_FILE, SHARED_DATABASE_FILE)
    shared_db = sqlite3.connect(clean_path(SHARED_DATABASE_FILE))

    for i in hash_data:
        book_hash = i[0]
        data = i[1]
        pdfpath = i[2]
        filename = pdfpath.split('\\')[-1]

        print(f"{filename[:90]}{'.'*(10 + max(0, 90 - len(filename)))}", end='')

        path_hashes = sioyek.get_path_hash_map()
        hash_paths = {value: key for key, value in path_hashes.items()}

        try:
            local_book_path = hash_paths[book_hash]
        except:
            print("skipping - file hash not found (has PDF ever been opened in Sioyek?)")
            continue

        try:
            doc = sioyek.get_document(local_book_path)
        except:
            print("skipping - file not found")
            continue

        highlights = [entry for entry in data['annotations'].values()]

        colors = {
            'red': 'r',
            'orange': 'o',
            'yellow': 'y',
            'green': 'f',
            'olive': 'g',
            'cyan': 's',
            'blue': 'b',
            'purple': 'v',
            'gray': 'k', # for true gray set to 'i'
            'undefined': 'k'          
        }

        new_count = 0
        succ_count = 0
        for hi in highlights:
            try:
                if shared_db.execute("SELECT document_path FROM highlights WHERE document_path = ? AND desc = ?", (book_hash, hi['text'])).fetchone():
                    continue

                # correct y value
                pboxes = [int(i) for i in hi['pboxes'].keys()]
                min_pbox = str(min(pboxes))
                max_pbox = str(max(pboxes))
                
                y0 = hi['pboxes'][min_pbox]['y']
                y1 = hi['pboxes'][max_pbox]['y']
                y0_correction = hi['pboxes'][min_pbox]['h'] / 2
                y1_correction = hi['pboxes'][max_pbox]['h'] / 2

                y0 += y0_correction
                y1 += y1_correction

                # convert to abs pos
                offset_x = (doc.page_widths[hi['page'] - 1]) / 2
                begin_pos = DocumentPos(hi['page'] - 1, hi['pos0']['x'] - offset_x, y0)
                end_pos = DocumentPos(hi['page'] - 1, hi['pos1']['x'] - offset_x, y1)
                (hi['begin'], hi['end']) = (doc.to_absolute(begin_pos), doc.to_absolute(end_pos))

                hi_color = colors[hi.get('color', 'undefined')]
                hi_uuid = str(uuid.uuid4())


                Q_HI_INSERT ="""
                INSERT INTO highlights (document_path, desc, type, text_annot, creation_time, modification_time, uuid, begin_x, begin_y, end_x, end_y)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                params = (book_hash, hi['text'], hi_color, hi.get('note', ''), hi['datetime'], hi.get('datetime_updated', ''), hi_uuid, hi['begin'].offset_x, hi['begin'].offset_y, hi['end'].offset_x, hi['end'].offset_y)

                # print(Q_HI_INSERT)
                shared_db.execute(Q_HI_INSERT, params)
                shared_db.execute('commit')

                succ_count += 1
            except ValueError as e:
                print(f'[ValueError: {e}] ', end='')
                continue
            except Exception as e:
                print(f'[Error: {e}] ', end='')
                continue

        print(f"transferred {succ_count} / {new_count} new highlights") if new_count > 0 else print("no new highlights")

    shared_db.close()
    sioyek.close()

if __name__ == "__main__":
    main()