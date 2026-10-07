"""commandagi.design.media declares a video or a song as the media editors' own graphs — the same nodes the
TypeScript SDK's media.ts declares from JSX — and each node carries the call that made it where media.ts puts an
element's source. Run: python -m unittest discover -s tests"""
import unittest

from commandagi.design import run_module
from commandagi.design.media import (clip, declare_song, declare_video, effect, gain, keyframe, marker, note, pitch_name, pitch_of, reverb,
                                     sampler, song, synth, title, track, transition, video)


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

    def test_a_song_holds_audio_clips_a_sampler_and_a_cycle(self):
        n = declare_song(song(
            track(gain(gain=0.5), clip(src="media/tone.wav", start=2, length=3, in_=0.25, volume=0.8), clip(src="media/tone.wav", name="Again", start=8),
                  name="Tone"),
            track(sampler(src="media/tone.wav", root="C5", release=1), clip(note(pitch="E5")), name="Bells"),
            cycle_start=4, cycle_end=12))["nodes"]
        self.assertEqual(n["master"]["inputs"]["cycle"], {"start": 4, "end": 12})
        self.assertEqual(n["player_Tone"]["inputs"], {"name": "Tone", "audio.1": wire("clip_tone", "audio"), "audio.2": wire("clip_Again", "audio")})
        self.assertEqual(n["fx_Tone_gain"]["inputs"]["audio"], wire("player_Tone", "audio"))
        self.assertEqual(n["clip_tone"]["inputs"], {"name": "tone", "src": "media/tone.wav", "start": 2, "length": 3, "offsetSeconds": 0.25, "gain": 0.8, "loop": False})
        self.assertEqual(n["inst_Bells"]["inputs"]["spec"], {"kind": "sampler", "src": "media/tone.wav", "baseNote": 72, "gain": 1,
                                                             "env": {"attack": 0.01, "decay": 0.15, "sustain": 0.6, "release": 1}})
        self.assertEqual(n["inst_Bells"]["inputs"]["midi.1"], wire("clip_Bells_1", "midi"))
        for bad, message in [(track(clip(src="/abs/tone.wav")), "relative to this file"), (track(clip(src="take.mp4")), "not a sound file"),
                             (track(synth(), clip(src="tone.wav")), "goes on a track without one"),
                             (track(clip(src="tone.wav"), clip()), "need a <synth> or a <sampler>"), (track(sampler(src="a.wav", root="Q")), "root is the pitch")]:
            with self.assertRaisesRegex(ValueError, message):
                declare_song(song(bad))
        with self.assertRaisesRegex(ValueError, "names both"):
            declare_song(song(cycle_start=4))
        with self.assertRaisesRegex(ValueError, "comes after"):
            declare_song(song(cycle_start=4, cycle_end=4))

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
