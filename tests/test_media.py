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

    def test_a_video_file_on_an_audio_track_is_its_sound_and_a_link_pairs_picture_and_sound(self):
        take = dict(src="media/take.mp4", link="L1", start=1, out=4)
        n = declare_video(video(track(clip(volume=0, **take), name="V1"), track(clip(**take), name="A1", kind="audio")))["nodes"]
        clips = [x["inputs"] for x in n.values() if x["type"] == "video.clip"]
        self.assertEqual([(c["kind"], c["link"], c["volume"]) for c in clips], [("video", "L1", 0), ("audio", "L1", 1)])
        with self.assertRaisesRegex(ValueError, "a picture goes on a video track"):
            declare_video(video(track(clip(src="a.png", duration=1), kind="audio")))

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

    def test_a_composition_is_another_video_by_path_and_an_artboard_a_drawings_page(self):
        from commandagi.design.media import artboard, composition, intro
        n = declare_video(video(track(
            composition(intro(preset="fade"), src="parts/Intro.vid.tsx", start=1, in_=0.5, out=2.5, inputs={"hue": 30}),
            artboard(src="Poster.draw.tsx", start=3, duration=2, view="page_2", fit="cover", opacity=0.5), name="V1")))["nodes"]
        self.assertEqual(n["comp_Intro.vid.tsx"], {"id": "comp_Intro.vid.tsx", "type": "video.instance", "label": "Intro.vid.tsx",
                                                   "inputs": {"__instance": {"path": "parts/Intro.vid.tsx", "name": "Intro.vid.tsx"}, "hue": 30}})
        comp = n["clip_Intro.vid.tsx"]
        self.assertEqual(comp["inputs"]["source"], wire("comp_Intro.vid.tsx", "frames"))
        self.assertEqual(comp["inputs"]["kind"], "video")
        self.assertEqual(comp["inputs"]["duration"], 2)
        self.assertEqual(comp["inputs"]["inPoint"], 0.5)
        self.assertNotIn("assetId", comp["inputs"], "a composition is no media file")
        self.assertEqual(set(comp["meta"]["sources"]), {"intro"})
        art = n["clip_Poster.draw.tsx"]["inputs"]
        self.assertEqual(art["kind"], "renderable")
        self.assertEqual(art["renderable"], {"ref": {"locator": "Poster.draw.tsx", "fileKind": "drawing", "representation": "auto", "view": "page_2"}, "fit": "cover"})
        self.assertIsNone(art["source"])
        self.assertEqual(art["opacity"], 0.5)
        cropped = declare_video(video(track(artboard(src="Poster.draw.tsx", duration=2, crop={"x": 10, "y": 20, "width": 400, "height": 300}))))["nodes"]
        self.assertEqual(cropped["clip_Poster.draw.tsx"]["inputs"]["renderable"]["crop"], {"x": 10, "y": 20, "width": 400, "height": 300})
        with self.assertRaisesRegex(ValueError, r"crop is \{ x, y, width, height \}"):
            declare_video(video(track(artboard(src="P.draw.tsx", duration=2, crop={"x": 0, "y": 0, "width": 0, "height": 3}))))
        given = declare_video(video(track(artboard(src="Poster.draw.tsx", duration=2, inputs={"title": "Square", "size": 40, "dark": True}))))["nodes"]
        self.assertEqual(given["clip_Poster.draw.tsx"]["inputs"]["renderable"]["ref"]["overrides"], {"title": "Square", "size": 40, "dark": True})
        with self.assertRaisesRegex(ValueError, r"inputs is \{ parameter: number \| text \| true/false \}"):
            declare_video(video(track(artboard(src="P.draw.tsx", duration=2, inputs={"size": [1]}))))
        refused = [
            (composition(src="Intro.mp4", out=1), "is not another video's code"),
            (composition(src="/x/Intro.vid.tsx", out=1), "relative to this file"),
            (composition(src="Intro.vid.tsx"), r"give its out \(or duration\)"),
            (composition(src="Intro.vid.tsx", out=1, inputs={"hue": "red"}), r"inputs is \{ parameter: number \}"),
            (composition(gain(), src="Intro.vid.tsx", out=1), "has no sound"),
            (artboard(src="Poster.png", duration=1), "is not a drawing's code"),
            (artboard(src="Poster.draw.tsx"), "give its duration"),
            (artboard(src="Poster.draw.tsx", duration=1, fit="stretch"), "fit is one of fill, contain, cover, none"),
        ]
        for el, why in refused:
            with self.assertRaisesRegex(ValueError, why):
                declare_video(video(track(el)))
        with self.assertRaisesRegex(ValueError, "an artboard goes on a video track"):
            declare_video(video(track(artboard(src="P.draw.tsx", duration=1), kind="audio")))

    def test_a_videos_own_artboards_and_the_overrides_a_clip_title_or_effect_sets_on_one(self):
        from commandagi.design.media import artboard, override
        n = declare_video(video(
            track(
                clip(override(artboard="Vertical", src="media/tall.mp4"),
                     effect(override(artboard="Vertical", amount=0.6), type="vignette", amount=0.3), src="media/wide.mp4", out=4),
                title(override(artboard="Vertical", y=700, scale_x=0.8, font_size=64, crop_left=0.1), text="Hello", start=4, duration=2, y=300),
                name="V1"),
            artboard(name="Vertical", width=1080, height=1920),
            width=1920, height=1080))
        nodes = n["nodes"]
        self.assertEqual(nodes["composite"]["inputs"]["artboards"], [{"name": "Vertical", "width": 1080, "height": 1920}])
        clip_ = nodes["clip_wide.mp4"]
        self.assertEqual(clip_["inputs"]["overrides"], {"Vertical": {"assetId": "media_tall.mp4"}})
        self.assertEqual(nodes["src_media_tall.mp4"]["inputs"]["__asset"], {"kind": "file", "$file": "media/tall.mp4"})
        self.assertEqual(clip_["inputs"]["effects"][0]["overrides"], {"Vertical": {"params": {"amount": 0.6}}})
        self.assertEqual(nodes["clip_Title"]["inputs"]["overrides"],
                         {"Vertical": {"transform": {"y": 700, "scaleX": 0.8}, "crop": {"left": 0.1}, "text": {"fontSize": 64}}})
        vertical = artboard(name="Vertical", width=1080, height=1920)
        refused = [
            (override(artboard="Square", x=1), 'declares no <artboard name="Square">'),
            (override(artboard="Vertical"), "names what it sets"),
            (override(artboard="Vertical", volume=0.5), "prop volume is not read on a <override>"),
        ]
        for el, why in refused:
            with self.assertRaisesRegex(ValueError, why):
                declare_video(video(track(title(el, text="T", duration=1)), vertical))
        with self.assertRaisesRegex(ValueError, "an artboard of a drawing goes on a <track>"):
            declare_video(video(artboard(src="Poster.draw.tsx", duration=1)))
        with self.assertRaisesRegex(ValueError, r"b\.png is not a video file"):
            declare_video(video(track(clip(override(artboard="V", src="b.png"), src="a.mp4", out=1)), artboard(name="V", width=1, height=1)))
