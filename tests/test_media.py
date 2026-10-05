"""commandagi.design.media declares a video or a song as the media editors' own graphs — the same nodes the
TypeScript SDK's media.ts declares from JSX. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.media import clip, effect, keyframe, marker, note, reverb, song, synth, title, track, transition, video, pitch_name, pitch_of


def wire(node, port):
    return {"wire": {"node": node, "port": port}}


class VideoTests(unittest.TestCase):
    def test_a_video_declares_sources_clips_tracks_and_the_composite(self):
        g = run_module(
            "from commandagi.design.media import *\n"
            "result = video(\n"
            "  track(clip(transition(kind='crossDissolve', duration=0.5), keyframe(property='opacity', time=0, value=0),\n"
            "             src='media/take.webm', start=1, in_=2, out=6, speed=2),\n"
            "        title(text='Hello', start=0, duration=2, fontSize=48), name='V1'),\n"
            "  track(clip(src='media/tone.wav', duration=3, volume=0.5), name='A1', kind='audio'),\n"
            "  marker(time=4, name='Drop'), name='Cut', fps=25)\n",
            "cut.vid.py",
        )["graph"]
        n = g["nodes"]
        self.assertEqual(n["src_media_take.webm"]["inputs"]["__asset"], {"kind": "file", "$file": "media/take.webm"})
        self.assertEqual(n["clip_take.webm"]["inputs"]["duration"], 2)
        self.assertEqual(n["clip_take.webm"]["inputs"]["source"], wire("src_media_take.webm", "media"))
        self.assertEqual(n["clip_take.webm"]["inputs"]["transitionIn"], {"kind": "crossDissolve", "duration": 0.5})
        self.assertEqual(n["clip_take.webm"]["inputs"]["keyframes"], [{"property": "opacity", "keys": [{"id": "kf_clip_take.webm", "time": 0, "value": 0, "easing": "linear"}]}])
        self.assertEqual(n["clip_Title"]["inputs"]["text"]["fontSize"], 48)
        self.assertEqual(n["track_V1"]["inputs"]["clips.2"], wire("clip_Title", "frames"))
        self.assertEqual(n["composite"]["inputs"]["tracks.1"], wire("track_V1", "frames"))
        self.assertEqual(n["composite"]["inputs"]["markers"], [{"id": "marker_1", "time": 4, "name": "Drop", "color": "#f5c542"}])

    def test_what_a_video_cannot_say_is_refused_by_name(self):
        from commandagi.design.media import declare_video
        with self.assertRaisesRegex(ValueError, "relative to this file"):
            declare_video(video(track(clip(src="/abs/a.mp4", duration=1))))
        with self.assertRaisesRegex(ValueError, "a sound goes on an audio track"):
            declare_video(video(track(clip(src="a.wav", duration=1))))
        with self.assertRaisesRegex(ValueError, "prop trackers is not read"):
            declare_video(video(track(clip(src="a.mp4", out=2, trackers=[]))))
        with self.assertRaisesRegex(ValueError, "<effect> names its type"):
            declare_video(video(track(clip(effect(), src="a.mp4", out=2))))


class SongTests(unittest.TestCase):
    def test_a_song_declares_the_chain_and_inline_notes(self):
        from commandagi.design.media import declare_song
        g = declare_song(song(track(synth(wave="triangle", attack=0.02), reverb(mix=0.5),
                                    clip(note(pitch="C4", start=0, duration=1), note(pitch=64, start=1), start=4), name="Keys"),
                              name="Loop", tempo=96, timeSignature="3/4")).ir
        n = g["nodes"]
        self.assertEqual(n["master"]["inputs"]["tempo"], [{"atBeat": 0, "bpm": 96}])
        self.assertEqual(n["master"]["inputs"]["timeSig"], {"num": 3, "den": 4})
        self.assertEqual(n["master"]["inputs"]["audio.1"], wire("track_Keys", "audio"))
        self.assertEqual(n["track_Keys"]["inputs"]["audio"], wire("fx_Keys_reverb", "audio"))
        self.assertEqual(n["inst_Keys"]["inputs"]["midi.1"], wire("clip_Keys_1", "midi"))
        self.assertEqual(n["clip_Keys_1"]["inputs"]["notes"], [
            {"id": "clip_Keys_1_n1", "pitch": 60, "start": 0, "dur": 1, "vel": 0.8},
            {"id": "clip_Keys_1_n2", "pitch": 64, "start": 1, "dur": 1, "vel": 0.8},
        ])
        self.assertEqual(pitch_of("F#3"), 54)
        self.assertEqual(pitch_name(61), "C#4")
        with self.assertRaisesRegex(ValueError, "need a <synth>"):
            declare_song(song(track(clip())))


if __name__ == "__main__":
    unittest.main()
