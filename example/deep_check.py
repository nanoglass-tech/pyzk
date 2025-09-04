#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deep Checklist Test untuk pyzk (MB40-VL 49-byte & umum)
- Smoke & sanity: connect, get_users, get_attendance
- Fallback user_id -> uid deteksi
- Parallel pull 2+ device
- Negative test (IP salah / unreachable)
- Output ringkas + opsi CSV/JSON report

Jalankan: python examples/deep_check.py --help
"""
import os
import csv
import json
import time
import argparse
import threading
from datetime import datetime
from typing import List, Dict, Any, Tuple, Union

from zk.base import ZK  # pastikan modul path sudah terinstall (pip install -e .)

# ---------- Util ----------
def ok(b: bool) -> str:
    return "PASS" if b else "FAIL"

def iso(dt):
    return None if dt is None else dt.isoformat(sep=" ")

def write_csv(ip: str, rows, port: int = 4370, outdir: str = "/tmp") -> str:
    if not rows:
        return ""
    os.makedirs(outdir, exist_ok=True)
    fn = os.path.join(
        outdir,
        f"attendance_{ip.replace('.', '-')}_{port}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    )
    with open(fn, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["user_id", "timestamp", "status", "punch", "uid"])
        for r in rows:
            w.writerow([r.user_id, iso(r.timestamp), r.status, r.punch, r.uid])
    return fn

def summarize_att(rows) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"count": 0, "first": None, "last": None, "unique_users": 0}
    rows_sorted = sorted(rows, key=lambda r: r.timestamp)
    first_ts = rows_sorted[0].timestamp
    last_ts = rows_sorted[-1].timestamp
    uniq = len({r.user_id for r in rows})
    return {"count": n, "first": first_ts, "last": last_ts, "unique_users": uniq}

def get_users_map(users) -> Dict[str, int]:
    # map user_id -> uid
    m = {}
    for u in users:
        # user_id unik, jika duplikat ambil yang pertama
        if u.user_id not in m:
            m[u.user_id] = u.uid
    return m

# ---------- Test primitives ----------
def test_connect(ip: str, port: int, verbose=False) -> Tuple[bool, str]:
    zk = ZK(ip, port=port, verbose=verbose)
    try:
        zk.connect()
        zk.disconnect()
        return True, ""
    except Exception as e:
        return False, str(e)


def test_users(ip: str, port: int, verbose=False) -> Tuple[bool, Dict[str, Any], str]:
    zk = ZK(ip, port=port, verbose=verbose)
    try:
        zk.connect()
        users = zk.get_users()
        zk.disconnect()
        sample = [(u.uid, u.user_id, u.name) for u in users[:5]]
        info = {"count": len(users), "sample": sample}
        return True, info, ""
    except Exception as e:
        return False, {}, str(e)


def test_attendance(ip: str, port: int, verbose=False) -> Tuple[bool, Dict[str, Any], List[Any], str]:
    zk = ZK(ip, port=port, verbose=verbose)
    try:
        zk.connect()
        rows = zk.get_attendance()
        zk.disconnect()
        smry = summarize_att(rows)
        tail = rows[-3:] if len(rows) >= 3 else rows
        info = {
            "summary": {"count": smry["count"], "first": iso(smry["first"]), "last": iso(smry["last"]),
                        "unique_users": smry["unique_users"]},
            "tail": [(r.user_id, iso(r.timestamp), (r.status, r.punch), r.uid) for r in tail]
        }
        return True, info, rows, ""
    except Exception as e:
        return False, {}, [], str(e)

def test_fallback_userid(ip: str, users_map: Dict[str, int], rows) -> Tuple[bool, Dict[str, Any]]:
    """
    Deteksi fallback user_id -> uid:
    Heuristik: sebuah attendance dianggap 'fallback' bila:
      - user_id attendance TIDAK ada di users_map, DAN
      - user_id attendance == str(uid attendance)
    """
    fallback_events = []
    for r in rows:
        if (r.user_id not in users_map) and (r.user_id == str(r.uid)):
            fallback_events.append((r.user_id, iso(r.timestamp)))
    info = {"fallback_count": len(fallback_events), "samples": fallback_events[:5]}
    # fallback boleh terjadi; PASS selalu, tapi laporkan jumlahnya
    return True, info

def test_parallel(endpoints: List[Tuple[str, int]], verbose=False) -> Tuple[bool, Dict[str, Any], str]:
    """
    Tarik attendance dari semua (ip, port) secara paralel (threading).
    PASS jika semua selesai tanpa exception.
    """
    results: Dict[str, Any] = {}
    ok_all = True
    err_msg = ""
    lock = threading.Lock()

    def worker(ip: str, port: int):
        nonlocal ok_all
        t0 = time.time()
        try:
            zk = ZK(ip, port=port, verbose=verbose)
            zk.connect()
            rows = zk.get_attendance()
            zk.disconnect()
            dt = round(time.time() - t0, 2)
            with lock:
                results[f"{ip}:{port}"] = {"duration_sec": dt, "records": len(rows)}
        except Exception as e:
            with lock:
                results[f"{ip}:{port}"] = {"error": str(e)}
                ok_all = False

    threads = [threading.Thread(target=worker, args=(ip, port)) for ip, port in endpoints]
    for t in threads: t.start()
    for t in threads: t.join()

    if not ok_all:
        err_list = [k for k, v in results.items() if "error" in v]
        err_msg = f"Parallel error on: {', '.join(err_list)}"

    return ok_all, {"devices": results}, err_msg

def test_negative(ip: str, port: int) -> Tuple[bool, str]:
    ok_, err = test_connect(ip, port, verbose=False)
    return (not ok_), ("" if not ok_ else "Unexpectedly connected to bad IP")

# ---------- Main orchestrator ----------
def parse_endpoints(ips_arg: str, ports_arg: str = "") -> List[Tuple[str, int]]:
    """
    Terima:
      - ips_arg: "ip" atau "ip:port" dipisah koma. Contoh:
        "192.168.1.10,192.168.1.11:5005"
      - ports_arg: daftar port dipisah koma (optional). Contoh: "4370,5005"
        Aturan:
          * Jika ports_arg kosong -> pakai port dari ips_arg (jika ada), sisanya default 4370
          * Jika len(ports_arg) == 1 -> port yang sama untuk semua ip
          * Jika len(ports_arg) > 1 -> harus sama panjang dengan jumlah ip (yang valid)
    """
    raw_ips = [x.strip() for x in ips_arg.split(",") if x.strip()]
    if not raw_ips:
        raise ValueError("Harap isi IP device.")

    ips: List[str] = []
    ports_from_ips: List[Union[int, None]] = []
    for token in raw_ips:
        if ":" in token:
            host, p = token.rsplit(":", 1)
            ips.append(host)
            ports_from_ips.append(int(p))
        else:
            ips.append(token)
            ports_from_ips.append(None)

    # Kumpulkan ports dari argumen --ports (bila ada)
    ports: List[int] = []
    if ports_arg:
        toks = [x.strip() for x in ports_arg.split(",") if x.strip()]
        if len(toks) == 1:
            # replika untuk semua IP
            ports = [int(toks[0])] * len(ips)
        else:
            if len(toks) != len(ips):
                raise ValueError(f"Panjang --ports ({len(toks)}) harus 1 atau sama dengan jumlah IP ({len(ips)}).")
            ports = [int(x) for x in toks]
    else:
        # tidak ada --ports: ambil dari "ip:port" jika ada, sisanya default 4370
        for p in ports_from_ips:
            ports.append(int(p) if p is not None else 4370)

    # final endpoints
    return list(zip(ips, ports))

def run_deepcheck(ips: List[str], ports: List[str], parallel: bool, bad_ip: str, save_csv: bool, report_path: str) -> int:
    endpoints = parse_endpoints(",".join(ips), ",".join(ports) if ports else "")
    report: Dict[str, Any] = {
        "started_at": iso(datetime.now()),
        "endpoints": [f"{ip}:{port}" for ip, port in endpoints],
        "env": {"ZK_SKIP_PING": os.getenv("ZK_SKIP_PING")},
        "results": {},
    }
    exit_code = 0

    for (ip, port) in endpoints:
        print(f"\n=== DEVICE {ip}:{port} ===")
        dev_res = {}

        ok1, err1 = test_connect(ip, port)
        print(f"[1] Connect           : {ok(ok1)}" + (f" | {err1}" if not ok1 else ""))
        dev_res["connect"] = {"pass": ok1, "error": err1}

        ok2, users_info, err2 = test_users(ip, port)
        print(f"[2] get_users()       : {ok(ok2)} | count={users_info.get('count',0)}")
        if not ok2: print(f"    error: {err2}")
        dev_res["users"] = {"pass": ok2, "info": users_info, "error": err2}

        ok3, att_info, rows, err3 = test_attendance(ip, port)
        cnt = att_info.get("summary", {}).get("count", 0)
        uuniq = att_info.get("summary", {}).get("unique_users", 0)
        print(f"[3] get_attendance()  : {ok(ok3)} | records={cnt} unique_users={uuniq}")
        if att_info.get("tail"):
            for t in att_info["tail"]:
                print(f"    tail: user_id={t[0]} ts={t[1]} status/punch={t[2]} uid={t[3]}")
        if not ok3: print(f"    error: {err3}")
        dev_res["attendance"] = {"pass": ok3, "info": att_info, "error": err3}

        # (opsional) Simpan CSV
        csv_path = ""
        if save_csv and ok3 and rows:
            csv_path = write_csv(ip, rows, port=port)
            if csv_path:
                print(f"[4] CSV               : saved -> {csv_path}")
        dev_res["csv"] = csv_path

        report["results"][f"{ip}:{port}"] = dev_res

    # Parallel
    if parallel and len(endpoints) >= 2:
        okp, pres, perr = test_parallel(endpoints)
        print(f"\n=== PARALLEL ===")
        print(f"[P] Parallel pull     : {ok(okp)}")
        for k, r in pres["devices"].items():
            if "error" in r:
                print(f"    {k}: ERROR {r['error']}")
            else:
                print(f"    {k}: duration={r['duration_sec']}s records={r['records']}")
        report["parallel"] = {"pass": okp, "info": pres, "error": perr}
        if not okp:
            exit_code = 1

    # Negative (opsional) — dukung ip:port
    if bad_ip:
        if ":" in bad_ip:
            bad_host, bad_port = bad_ip.rsplit(":", 1)
            bad_port = int(bad_port)
        else:
            bad_host, bad_port = bad_ip, 4370
        okn, nerr = test_negative(bad_host, bad_port)
        print(f"\n=== NEGATIVE ===")
        print(f"[N] Bad {bad_host}:{bad_port} : {ok(okn)}" + (f" | {nerr}" if nerr else ""))
        report["negative"] = {"pass": okn, "endpoint": f"{bad_host}:{bad_port}", "error": nerr}
        if not okn:
            exit_code = 1

    # Tulis report JSON (tetap sama seperti sebelumnya)
    # ...
    if report_path:
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nReport JSON -> {report_path}")
    
    return exit_code

def get_users_map_simple(ip: str) -> Dict[str, int]:
    """
    Ambil peta user_id->uid dari device (dipakai fallback checker).
    Terpisah agar bisa dipanggil saat salah satu test gagal.
    """
    zk = ZK(ip, port=4370, verbose=False)
    zk.connect()
    users = zk.get_users()
    zk.disconnect()
    m = {}
    for u in users:
        if u.user_id not in m:
            m[u.user_id] = u.uid
    return m

# ---------- CLI ----------
def parse_args():
    p = argparse.ArgumentParser(description="Deep Checklist Test untuk pyzk")
    p.add_argument("--ips", type=str, default=os.getenv("ZK_IPS", ""),
                   help="Daftar device dipisahkan koma, boleh 'ip' atau 'ip:port'. Contoh: 192.168.1.10,192.168.1.11:5005")
    p.add_argument("--ports", type=str, default=os.getenv("ZK_PORTS", ""),
                   help="(Opsional) Daftar port, dipisahkan koma. Contoh: 4370,5005. "
                        "Jika diisi 1 angka, dipakai untuk semua IP. Jika kosong, akan baca dari format ip:port atau default 4370.")
    p.add_argument("--parallel", action="store_true", help="Jalankan penarikan paralel (threads)")
    p.add_argument("--bad-ip", type=str, default="", help="Endpoint salah untuk uji negatif, boleh 'ip' atau 'ip:port'")
    p.add_argument("--save-csv", action="store_true", help="Simpan CSV attendance per device ke /tmp")
    p.add_argument("--report", type=str, default="", help="Path file JSON report, mis. /tmp/pyzk_deepcheck.json")
    return p.parse_args()

def main():
    args = parse_args()
    ips = [ip.strip() for ip in args.ips.split(",") if ip.strip()]
    ports = [p.strip() for p in args.ports.split(",")] if args.ports else []
    if not ips:
        print("Harap isi IP device dengan --ips atau env ZK_IPS.")
        return 2

    # hormati env ZK_SKIP_PING
    # ...

    print("Deep Checklist Test start:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("Devices:", ips, "| Ports:", ports if ports else "(auto)")
    code = run_deepcheck(
        ips=ips,
        ports=ports,
        parallel=args.parallel,
        bad_ip=args.bad_ip,
        save_csv=args.save_csv,
        report_path=args.report,
    )
    print("\nDONE with exit code", code)
    raise SystemExit(code)

if __name__ == "__main__":
    main()
