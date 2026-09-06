import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import SiteClient, export_transcript, playlist, renditions, srt_time, validate_job


class EngineTests(unittest.TestCase):
    def test_completion_sends_valid_json_to_the_api(self):
        job = dict(protocol=1, jobId='11111111-1111-4111-8111-111111111111', token='a' * 43, kind='video', apiUrl='http://localhost:4000/api/v1')
        client = SiteClient(job, threading.Event(), lambda _: None)
        with patch.object(client.opener, 'open', return_value=io.BytesIO(b'{"completed":true}')) as opened:
            self.assertTrue(client.request('POST', '/complete')['completed'])
            request = opened.call_args.args[0]
            self.assertEqual(json.loads(request.data), {})
            self.assertEqual(request.get_header('Content-type'), 'application/json')

    def test_no_upscaling_and_all_qualities(self):
        self.assertEqual([r['height'] for r in renditions(3840, 2160, True)], [360, 480, 720, 1080, 1440])
        self.assertEqual(renditions(320, 240, False), [dict(label='240p', height=240, width=320, bitrate=500000, audioBitrate=0)])

    def test_srt_carries_millisecond_rounding_and_polish_text(self):
        self.assertEqual(srt_time(59.9996), '00:01:00,000')
        with tempfile.TemporaryDirectory() as folder:
            export_transcript(Path(folder), {'segments': [dict(start=0.125, end=3.789, text='Zażółć gęślą jaźń.')]})
            self.assertIn('00:00:00,125 --> 00:00:03,789', (Path(folder) / 'transcript.srt').read_text(encoding='utf-8'))
            self.assertIn('Zażółć', (Path(folder) / 'transcript.txt').read_text(encoding='utf-8'))

    def test_job_rejects_unsafe_destinations(self):
        job = dict(protocol=1, jobId='11111111-1111-4111-8111-111111111111', token='a' * 43, kind='video')
        for url in ['http://example.com/api/v1', 'https://user:password@example.com/api/v1', 'file:///api/v1', 'https://example.com/api/v1?x=1']:
            with self.assertRaises(ValueError):
                validate_job(dict(job, apiUrl=url))
        validate_job(dict(job, apiUrl='http://localhost:4000/api/v1'))
        validate_job(dict(job, apiUrl='https://example.com/api/v1'))

    def test_upload_resumes_from_server_confirmed_files(self):
        job = dict(protocol=1, jobId='11111111-1111-4111-8111-111111111111', token='a' * 43, kind='video', apiUrl='https://example.com/api/v1')
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'remaining.ts').write_bytes(b'payload')
            manifest = {'files': [dict(path='done.ts', size=7, sha256='0' * 64), dict(path='remaining.ts', size=7, sha256=hashlib.sha256(b'payload').hexdigest())]}
            client = SiteClient(job, threading.Event(), lambda _: None)
            with patch.object(client, 'request', side_effect=[dict(completed=False, stale=False, uploaded=['done.ts']), {}, {}, {}]) as request:
                client.upload(Path(folder), manifest)
                self.assertEqual([call.args[0] for call in request.call_args_list], ['GET', 'POST', 'PUT', 'POST'])
                self.assertEqual(request.call_args_list[2].args[1], '/files/remaining.ts')

    def test_playlist_contains_relative_segments_and_whole_duration(self):
        row = dict(label='360p', width=640, height=360, bitrate=800000, audioBitrate=96000, durations=[6.0, 1.25])
        manifest = dict(renditions=[row])
        content = playlist(manifest, '360p/index.m3u8')
        self.assertIn('#EXTINF:1.250000,\nsegment_000001.ts', content)
        self.assertTrue(content.endswith('#EXT-X-ENDLIST\n'))
        self.assertNotIn('http', content)


if __name__ == '__main__':
    unittest.main()
