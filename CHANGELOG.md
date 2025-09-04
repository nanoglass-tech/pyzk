# Changelog (Fork)

> **Fork notice**  
> Repositori ini adalah **fork** dari upstream. Catatan di bawah **berlaku mulai `v0.6.0-ng1`**.  
> Riwayat sebelum itu adalah milik upstream dan dipertahankan utuh untuk keperluan audit/traceability.

## [Unreleased]

### Added

-   (isi jika ada perubahan yang sedang disiapkan)

### Changed

-   (isi jika ada perubahan perilaku yang kompatibel)

### Fixed

-   (isi jika ada perbaikan bug yang menunggu rilis)

---

## [0.6.0-ng1] - 2025-09-04

### Added

-   **Dukungan penuh ZKTeco MB40-VL (49-byte)**: parser `"<H24sB4sB12s5x>"` dengan fallback `user_id → uid` bila `user_id` kosong.
-   **Skrip uji mendalam**: `examples/deep_check.py` untuk validasi operasional **connect / get_users / get_attendance / parallel** dan ekspor **CSV** per endpoint (`ip` atau `ip:port`). :contentReference[oaicite:1]{index=1}

### Changed

-   **Kerapian logging**: hilangkan `print` liar; hormati `verbose=True` agar output default tetap bersih.

### Fixed

-   **Guard** `ZeroDivisionError` saat `records == 0`.
-   **Perbaikan util** `__reverse_hex` untuk Python 3 (integer division `//`, hindari nama argumen yang bentrok dengan built-in).

### Catatan

-   **Kompatibilitas**: tidak ada perubahan API publik kelas `ZK`; aplikasi downstream aman.
-   **Cara uji singkat**:
    ```bash
    source .venv/bin/activate
    export ZK_SKIP_PING=1
    python examples/deep_check.py \
      --ips "192.168.100.180:4370,192.168.100.176:43700" \
      --parallel --save-csv
    ```

# Changelog

## Version 0.9

-   Initial Python 3 Support
-   major changes

## Version 0.8

-   test suite tool (test_machine.py)
-   Initial TCP support

## Version 0.7

-   internal major changes

## Version 0.6

-   device password support

## Version 0.5

-   bug fixed get_users bug

## Version 0.4

-   bug fixed
-   minor update
-   update documentation

## Version 0.3

-   add function `get_serialnumber` (return device serial number)
-   add function `delete_user` (delete specific user by uid)
-   add function `clear_data` (format device)
-   add function `get_attendance` (get all attendance records)
-   add function `clear_attendance` (clear all attendance records)

## Version 0.2

-   add basic function and program fundamental
-   configure pypi
-   configure travis-ci integration

## Version 0.1

-   project initialization
