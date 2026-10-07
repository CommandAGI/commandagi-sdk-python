"""commandagi.design.media declares a video or a song as the media editors' own graphs — the same nodes the
TypeScript SDK's media.ts declares from JSX — and each node carries the call that made it where media.ts puts an
element's source. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.media import (clip, declare_song, declare_video, effect, keyframe, marker, note, pitch_name, pitch_of, reverb,
                                     song, synth, title, track, transition, video)


def wire(node, port):
    return {"wire": {"node": node, "port": port}}


class VideoTests(unittest.TestCase):
    def test_a_video_declares_sources_clips_tracks_and_the_composite(self):
        n = declare_video(video(
            track(clip(transition(kind="crossDissolve", duration=0.5), keyframe(property="opacity", time=0, value=0),
                       src="media/take.webm", start=1, in_=2, out=6, speed=2),
                  title(text="Hello", start=0, duration=2, font_size=48), name="V1"),
            track(clip(src="media/tone.wav", duration=3, volume=0.5), name="A1", kind="audio"),
            marker(time=4, name="Drop"), name="Cut", fps=25))["nodes"]
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
        with self.assertRaisesRegex(ValueError, "relative to this file"):
            declare_video(video(track(clip(src="/abs/a.mp4", duration=1))))
        with self.assertRaisesRegex(ValueError, "a sound goes on an audio track"):
            declare_video(video(track(clip(src="a.wav", duration=1))))
        with self.assertRaisesRegex(ValueError, "prop trackers is not read"):
            declare_video(video(track(clip(src="a.mp4", out=2, trackers=[]))))
        with self.assertRaisesRegex(ValueError, "<effect> names its type"):
            declare_video(video(track(clip(effect(), src="a.mp4", out=2))))
        with self.assertRaisesRegex(TypeError, "font_size"):
            title(text="Hi", fontSize=48)
        with self.assertRaisesRegex(TypeError, "<marker> holds nothing"):
            marker(note())

    def test_each_node_and_what_it_holds_carries_its_call(self):
        g = run_module(
            "from commandagi.design.media import clip, effect, keyframe, marker, track, transition, video\n"
            "result = video(\n"
            "    track(\n"
            "        clip(\n"
            "            transition(kind='cut'),\n"
            "            effect(type='vignette', amount=0.3),\n"
            "            keyframe(property='opacity', time=0, value=1),\n"
            "            src='media/a.png', duration=2,\n"
            "        ),\n"
            "        name='V1',\n"
            "    ),\n"
            "    marker(time=1),\n"
            ")\n",
            "cut.vid.py",
        )["graph"]
        n = g["nodes"]
        meta = n["clip_a.png"]["meta"]
        self.assertEqual((meta["source"]["tag"], meta["source"]["line"]), ("clip", 4))
        self.assertEqual({k: (v["tag"], v["line"]) for k, v in meta["sources"].items()},
                         {"transition": ("transition", 5), "effect:fx_vignette": ("effect", 6), "keyframe:kf_clip_a.png": ("keyframe", 7)})
        self.assertEqual(n["track_V1"]["meta"]["source"]["tag"], "track")
        self.assertEqual(n["composite"]["meta"]["source"]["line"], 2)
        self.assertEqual(n["composite"]["meta"]["sources"]["marker:marker_1"]["line"], 12)
        self.assertNotIn("meta", n["src_media_a.png"])  # a media file is no call of its own
        self.assertEqual(g["meta"]["sourceMap"]["language"], "py")


class SongTests(unittest.TestCase):
    def test_a_song_declares_the_chain_and_inline_notes(self):
        n = declare_song(song(track(synth(wave="triangle", attack=0.02), reverb(mix=0.5),
                                    clip(note(pitch="C4", start=0, duration=1), note(pitch=64, start=1), start=4), name="Keys"),
                              name="Loop", tempo=96, time_signature="3/4"))["nodes"]
        self.assertEqual(n["master"]["inputs"]["tempo"], [{"atBeat": 0, "bpm": 96}])
        self.assertEqual(n["master"]["inputs"]["timeSig"], {"num": 3, "den": 4})
        self.assertEqual(n["master"]["inputs"]["audio.1"], wire("track_Keys", "audio"))
        self.assertEqual(n["track_Keys"]["inputs"]["audio"], wire("fx_Keys_reverb", "audio"))
        self.assertEqual(n["track_Keys"]["meta"], {"order": 0})
        self.assertEqual(n["inst_Keys"]["inputs"]["midi.1"], wire("clip_Keys_1", "midi"))
        self.assertEqual(n["clip_Keys_1"]["inputs"]["notes"], [
            {"id": "clip_Keys_1_n1", "pitch": 60, "start": 0, "dur": 1, "vel": 0.8},
            {"id": "clip_Keys_1_n2", "pitch": 64, "start": 1, "dur": 1, "vel": 0.8},
        ])
        self.assertEqual(pitch_of("F#3"), 54)
        self.assertEqual(pitch_name(61), "C#4")
        with self.assertRaisesRegex(ValueError, "need a <synth>"):
            declare_song(song(track(clip())))

    def test_a_note_written_in_a_loop_names_its_one_call(self):
        n = run_module(
            "from commandagi.design.media import clip, note, song, synth, track\n"
            "result = song(track(synth(), clip(*[note(pitch=60 + i, start=i) for i in range(3)], name='Arp'), name='Keys'))\n",
            "loop.mus.py",
        )["graph"]["nodes"]
        meta = n["clip_Arp"]["meta"]
        self.assertEqual(meta["source"]["tag"], "clip")
        self.assertEqual(sorted(meta["sources"]), ["note:clip_Arp_n1", "note:clip_Arp_n2", "note:clip_Arp_n3"])
        self.assertEqual({v["evaluations"] for v in meta["sources"].values()}, {3})
        self.assertEqual(n["inst_Keys"]["meta"]["source"]["tag"], "synth")
        self.assertEqual(n["track_Keys"]["meta"]["order"], 0)
        self.assertEqual(n["track_Keys"]["meta"]["source"]["tag"], "track")
        self.assertEqual(n["master"]["meta"]["source"]["tag"], "song")


if __name__ == "__main__":
    unittest.main()


class VideoVocabularyTests(unittest.TestCase):
    def test_crop_a_lut_transition_settings_audio_effects_and_a_bezier_key(self):
        from commandagi.design.media import compressor, distortion, eq, filter, gain
        n = declare_video(video(
            track(clip(transition(kind="iris", duration=1, align="end", shape=2), effect(type="lut", src="looks/a.cube", amount=0.5),
                       filter(mode="highpass"), keyframe(property="opacity", time=0, value=1, easing="bezier", bezier=[0.4, 0, 0.2, 1]),
                       src="a.mp4", out=2, crop_left=0.1),
                  distortion(amount=0.2), name="V1"),
            compressor(ratio=2), gain(gain=0.5, enabled=False)))["nodes"]
        c = n["clip_a.mp4"]["inputs"]
        self.assertEqual(c["crop"], {"top": 0, "right": 0, "bottom": 0, "left": 0.1})
        self.assertEqual(c["transitionIn"], {"kind": "iris", "duration": 1, "params": {"align": "end", "shape": 2}})
        self.assertEqual(c["effects"], [{"id": "fx_lut", "type": "lut", "enabled": True, "params": {"amount": 0.5}, "src": "looks/a.cube"}])
        self.assertEqual(c["audioEffects"], [{"id": "afx_highpass", "type": "highpass", "enabled": True, "params": {"frequency": 300, "q": 1}}])
        self.assertEqual(c["keyframes"][0]["keys"][0]["bezier"], [0.4, 0, 0.2, 1])
        self.assertEqual(n["track_V1"]["inputs"]["audioEffects"][0]["params"], {"amount": 0.2, "mix": 1})
        self.assertEqual([e["type"] for e in n["composite"]["inputs"]["masterEffects"]], ["compressor", "gain"])
        with self.assertRaisesRegex(ValueError, "a LUT names its .cube file"):
            declare_video(video(track(clip(effect(type="lut"), src="a.mp4", out=1))))
        with self.assertRaisesRegex(ValueError, "has no sound"):
            declare_video(video(track(clip(eq(), src="a.png", duration=1))))
