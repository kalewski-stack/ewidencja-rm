import http.client
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from reelcut import server  # noqa: E402

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
H = {"X-Reelcut": "1"}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="reelcut_srv_"))
        cls.state = server.State(cls.tmp)
        server.Handler.state = cls.state
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def req(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host or f"127.0.0.1:{self.port}")
        for k, v in (headers or {}).items():
            conn.putheader(k, v)
        data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
        if data is not None:
            conn.putheader("Content-Length", str(len(data)))
        conn.endheaders(data)
        resp = conn.getresponse()
        out = (resp.status, dict(resp.getheaders()), resp.read())
        conn.close()
        return out

    def new_job(self):
        status, _, body = self.req("POST", "/api/job", {}, H)
        self.assertEqual(status, 200)
        return json.loads(body)["id"]

    # --- bezpieczeństwo ---
    def test_info_and_ui_are_served(self):
        status, _, body = self.req("GET", "/api/info")
        self.assertEqual(status, 200)
        info = json.loads(body)
        self.assertIn("rolka_DeuOaXKtPBb", [t["id"] for t in info["templates"]])
        status, hdr, body = self.req("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", hdr["Content-Type"])
        self.assertIn(b"Potnij", body)

    def test_foreign_host_header_is_rejected(self):
        self.assertEqual(self.req("GET", "/api/info", host="evil.example.com")[0], 403)
        self.assertEqual(self.req("GET", "/", host="evil.example.com:80")[0], 403)

    def test_local_host_variants_are_accepted(self):
        for host in (f"localhost:{self.port}", f"127.0.0.1:{self.port}", "localhost"):
            self.assertEqual(self.req("GET", "/api/info", host=host)[0], 200, host)

    def test_changes_require_custom_header(self):
        self.assertEqual(self.req("POST", "/api/job", {})[0], 403)
        self.assertEqual(self.req("PUT", "/api/job/abcdefabcdef/upload?role=video&name=a.mp4", b"x")[0], 403)
        self.assertEqual(self.req("DELETE", "/api/job/abcdefabcdef")[0], 403)

    def test_hostname_helper(self):
        self.assertEqual(server.hostname("127.0.0.1:8765"), "127.0.0.1")
        self.assertEqual(server.hostname("[::1]:8765"), "[::1]")
        self.assertEqual(server.hostname("localhost"), "localhost")

    def test_path_traversal_in_job_or_file_is_impossible(self):
        self.assertEqual(self.req("GET", "/files/../../etc/passwd")[0], 404)
        self.assertEqual(self.req("GET", "/files/000000000000/../../x")[0], 404)
        self.assertEqual(self.req("GET", "/api/job/zzzzzzzzzzzz")[0], 404)

    # --- wgrywanie ---
    def test_upload_rejects_non_video_extension(self):
        jid = self.new_job()
        status, _, body = self.req("PUT", f"/api/job/{jid}/upload?role=video&name=notatki.txt", b"abc", H)
        self.assertEqual(status, 400)
        self.assertIn("Nieobsługiwany", json.loads(body)["error"])

    def test_upload_sanitises_file_name(self):
        jid = self.new_job()
        status, _, body = self.req("PUT", f"/api/job/{jid}/upload?role=video&name=..%2F..%2Fevil.mp4", b"abc", H)
        self.assertEqual(status, 200)
        name = json.loads(body)["name"]
        self.assertEqual(name, "evil.mp4")
        self.assertTrue((self.state.jobs_dir / jid / "video" / "evil.mp4").exists())

    def test_start_without_video_is_refused(self):
        jid = self.new_job()
        self.assertEqual(self.req("POST", f"/api/job/{jid}/start", {}, H)[0], 409)

    def test_invalid_options_are_refused(self):
        jid = self.new_job()
        self.req("PUT", f"/api/job/{jid}/upload?role=video&name=a.mp4", b"abc", H)
        status, _, body = self.req("POST", f"/api/job/{jid}/start", {"captions": "rm -rf"}, H)
        self.assertEqual(status, 400)

    # --- pliki i zakresy bajtów ---
    def test_range_requests(self):
        jid = self.new_job()
        f = self.tmp / "dane.mp4"
        f.write_bytes(bytes(range(256)) * 4)  # 1024 B
        self.state.get(jid).served["video"] = f
        status, hdr, body = self.req("GET", f"/files/{jid}/video", headers={"Range": "bytes=10-19"})
        self.assertEqual((status, hdr["Content-Range"], body), (206, "bytes 10-19/1024", bytes(range(10, 20))))
        status, hdr, body = self.req("GET", f"/files/{jid}/video", headers={"Range": "bytes=-5"})
        self.assertEqual((status, body), (206, bytes([251, 252, 253, 254, 255])))
        status, hdr, body = self.req("GET", f"/files/{jid}/video", headers={"Range": "bytes=1000-"})
        self.assertEqual((status, len(body)), (206, 24))
        self.assertEqual(self.req("GET", f"/files/{jid}/video", headers={"Range": "bytes=5000-6000"})[0], 416)
        status, hdr, body = self.req("GET", f"/files/{jid}/video")
        self.assertEqual((status, len(body), hdr["Accept-Ranges"]), (200, 1024, "bytes"))
        self.assertEqual(self.req("HEAD", f"/files/{jid}/video")[2], b"")

    # --- cały obieg ---
    @unittest.skipUnless(HAVE_FFMPEG, "brak ffmpeg")
    def test_full_job_flow(self):
        src = self.tmp / "klip.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=25:d=13", "-f", "lavfi",
                        "-i", "sine=f=250:d=13", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(src)], check=True)
        jid = self.new_job()
        status, _, _ = self.req("PUT", f"/api/job/{jid}/upload?role=video&name=klip.mp4", src.read_bytes(), H)
        self.assertEqual(status, 200)
        status, _, body = self.req("POST", f"/api/job/{jid}/start", {"captions": "off", "max_zoom": 1.4}, H)
        self.assertEqual(status, 200, body)
        job = None
        for _ in range(240):
            time.sleep(0.5)
            job = json.loads(self.req("GET", f"/api/job/{jid}")[2])
            if job["state"] in ("done", "error"):
                break
        self.assertEqual(job["state"], "done", job)
        self.assertEqual(job["result"]["captions"], False)
        status, hdr, body = self.req("GET", f"/files/{jid}/video")
        self.assertEqual(status, 200)
        self.assertEqual(len(body), (self.state.out_dir / job["result"]["video"]).stat().st_size)
        self.assertFalse((self.state.jobs_dir / jid).exists(), "wgrane pliki powinny zostać posprzątane")


if __name__ == "__main__":
    unittest.main()
