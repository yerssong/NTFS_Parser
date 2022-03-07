# Coding by YES
# 추가하면 좋을것 : Non-resident + Resident따로 빼기, $종류대로 따로 설정하기, $index부분 추가하기  (다음주에 하기)
# Fix Array -> 여기에 교환하는 부분 넣으면 더 좋지 않을까?


from datetime import datetime, timedelta
import pandas as pd
import sqlite3
import os
import argparse

# Little-Endian방식을 Integer로 바꾸는 Func, int.from_byte 직접 구현
def ltoi(buf):
    x = 0
    for i in range(0, len(buf)):
        mul = 1
        for j in range(0, i):
            mul *= 256
        x += buf[i] * mul
    return x

# From integer to big-endian
def intTobig(val):
    return format(val, 'X')

# From Timestamp to Time
def TimeTrans(buf):
    dt = ltoi(buf)
    dt = intTobig(dt)
    us = int(dt, 16) / 10.
    return datetime(1601, 1, 1) + timedelta(microseconds=us)

# MFT Entry Parsing
def Entry_parsing(buf, x):
    fixup_offset = ltoi(buf[0x04:0x06])
    log_num = ltoi(buf[0x08:0x10])
    seq_num = ltoi(buf[0x10:0x12])
    real_size = ltoi(buf[0x18:0x1C])
    allo_size = ltoi(buf[0x1C:0x20])
    Entry_size = ltoi(buf[0x1C:0x20])
    Attr_Offset = ltoi(buf[0x14:0x16])
    is_deleted = ltoi(buf[0x16:0x18])
    base = ltoi(buf[0x20:0x28])
    Next_Attr = ltoi(buf[0x28:0x2A])

    if x == 1:
        print("MFT Entry")
        print("size :", Entry_size, "fixup:", fixup_offset, "log num : ", log_num, "seq_num", seq_num, "Offset :",
              Attr_Offset, "delete :", is_deleted, "Next :", Next_Attr, "base :", base, "allo_size :", allo_size,
              "real_size : ", real_size)

    return Entry_size, Attr_Offset, Next_Attr, base, is_deleted, real_size

# Fix_array를 원래의 자리로 돌리기 위한 func
def fix_array(buf):
    buff = bytearray(buf)
    buff[0x01FE] = buff[0x32]
    buff[0x01FF] = buff[0x33]
    buff[0x03FE] = buff[0x34]
    buff[0x03FF] = buff[0x35]

    return buff

# $Standard_information Parsing
def SIA_parsing(buf, offset, x):
    attr_length = ltoi(buf[offset + 0x04:offset + 0x08])
    res_attr = ltoi(buf[offset + 0x08:offset + 0x09])
    c_time = TimeTrans(buf[offset + 0x18:offset + 0x20])
    m_time = TimeTrans(buf[offset + 0x20:offset + 0x28])
    Mft_time = TimeTrans(buf[offset + 0x28:offset + 0x30])
    last_time = TimeTrans(buf[offset + 0x30:offset + 0x38])

    if x == 1:
        print(attr_length, res_attr, c_time, m_time, Mft_time, last_time)
    return c_time, m_time, Mft_time, last_time, attr_length, res_attr

# $Filename Parsing
def FN_parsing(buf, offset, x):
    if (ltoi(buf[offset:offset+4])) != 48:
        offset += ltoi(buf[offset+4:offset+8])

    attr_length = ltoi(buf[offset + 0x04:offset + 0x08])
    res_attr = ltoi(buf[offset + 0x08:offset + 0x09])
    parent_dir = ltoi(buf[offset + 0x18:offset + 0x1E])
    c_time = TimeTrans(buf[offset + 0x20:offset + 0x28])
    m_time = TimeTrans(buf[offset + 0x28:offset + 0x30])
    Mft_time = TimeTrans(buf[offset + 0x30:offset + 0x38])
    last_time = TimeTrans(buf[offset + 0x38:offset + 0x40])
    file_size = ltoi(buf[offset + 0x40:offset + 0x48])
    name_length = ltoi(buf[offset + 0x58:offset + 0x59])
    file_name = buf[offset + 0x5A:offset + 0x5A + name_length + name_length]

    if x == 1:
        print(ltoi(buf[offset:offset + 4]), attr_length, res_attr, c_time, m_time, Mft_time, last_time, file_size,
              file_name.decode('utf-16'), parent_dir)
    return c_time, m_time, Mft_time, last_time, file_size, file_name, file_name.decode('utf-16'), parent_dir

#Filepath Searching
def Filepath(buf, val):
    num = val
    path = []
    if num == 4294967295:                        #ffff ffff
        return 'none'
    while num != 0:
        num *= 0x400
        ent = Entry_parsing(buf[num:num + 0x400], 0)
        buff = fix_array(buf[num:num + 0x400])
        sia = SIA_parsing(buff, ent[1], 0)
        fn = FN_parsing(buff, ent[1] + sia[4], 0)
        if fn[6] != '.':
            path.append(fn[6])

        path.append('/')
        if fn[7] == 5:
            path.append('root')
            path.reverse()
            p = (''.join(path))
            return p
        else:
            num = fn[7]

def DBmake(conn):
    try:
        cur = conn.cursor()
        cur.execute("Create table MFT (file_name text, is_deleted int, file_full_path text, file_size int,_created_time timestamp, s_modified_time date timestamp, s_mft_modified_time timestamp, s_last_accessed_time timestamp, f_created_time timestamp, f_modified_time timestamp, f_mft_modified_time timestamp, f_last_accessed_time timestamp)")
        conn.commit()
    except sqlite3.OperationalError:
        print('DB already exists, Confirm your Directory')

def DBinsert(conn, data):
    cur = conn.cursor()
    query = "insert into MFT values ( ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    cur.execute(query, data)


def CSVmake(path):
    df = pd.DataFrame(
        columns=['file_name', 'is_delete', 'file_full_path', 'file_size', 's_created_time', 's_modified_time',
                 's_mft_modified_time', 's_last_accessed_time', 'f_created_time', 'f_modified_time',
                 'f_mft_modified_time', 'f_last_accessed_time'])

    df.to_csv(path + os.sep + 'result.csv')


#Main Func
def main(input_path, output_path):
    with open(input_path, "rb") as f:
        buf = f.read()
        size = len(buf)
        conn = sqlite3.connect(output_path + os.sep + "result.db")
        DBmake(conn)
        CSVmake(output_path)

        for i in range(0, size, 0x400):
            print()
            print(i / 0x400, "번째 parsing")
            ent = Entry_parsing(buf[i:i+0x400], 1)
            buff = fix_array(buf[i:i+0x400])
            # 12~15는 미래를 위한 영역, 주어진 $MFT는 16~23이 비어있는데, 왜인지는 발견 못했다.
            if buf[i:i+4].decode() != 'FILE' and i > 0xF000:
                break
            if ent[3] == 0:       #entry[3] : 변환이 안된 원래의 mft 추출하려는것(확장 X)
                sia = SIA_parsing(buff, ent[1], 1)
                fn = FN_parsing(buff, ent[1] + sia[4], 1)
                path = Filepath(buf, fn[7])
                print(path)
            else:
                print("\n------The end, or Check your File-----")
                break

            data = [str(fn[6]), ent[4], path, ent[5], sia[0], sia[1], sia[2], sia[3], fn[0], fn[1], fn[2], fn[3]]
            DBinsert(conn, data)
            df = pd.DataFrame([data])
            df.to_csv(output_path + os.sep + 'result.csv', mode='a', header=False, encoding='euc-kr')

        conn.commit()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MFT Parser, Input your File and result path')
    parser.add_argument('-i', type=str, help='Input your MFT File path')
    parser.add_argument('-o', type=str, help='Input your result path')

    args = parser.parse_args()

    main(args.i, args.o)
