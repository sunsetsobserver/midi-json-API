import base64
import io
import uvicorn
import pretty_midi
import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="MIDI Converter API",
    description="Convert MIDI <-> JSON with extended parameters (instruments, tempo, meter, etc.)",
    version="2.0.0",
)

@app.post("/convert-midi")
async def convert_midi(data: dict):
    """
    Accepts JSON with a base64-encoded MIDI file and returns a JSON structure that includes:
      - instruments: list of instruments (each with program, is_drum, channel, and their notes)
      - tempo_changes: list of tempo change events (time and tempo)
      - time_signatures: list of time signature changes (time, numerator, and denominator)
    """
    midi_b64 = data.get("midi_base64", None)
    if not midi_b64:
        return JSONResponse({"error": "No base64 MIDI provided."}, status_code=400)
    
    try:
        # Decode the base64 MIDI string into raw bytes and parse with PrettyMIDI
        midi_bytes = base64.b64decode(midi_b64)
        midi_data = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        
        # Extract instruments and their notes
        instruments_data = []
        for idx, instrument in enumerate(midi_data.instruments):
            notes_list = []
            for note in instrument.notes:
                notes_list.append({
                    "start": round(note.start, 3),
                    "duration": round(note.end - note.start, 3),
                    "pitch": note.pitch,
                    "velocity": note.velocity
                })
            instruments_data.append({
                "id": idx,
                "program": instrument.program,
                "is_drum": instrument.is_drum,
                # Since PrettyMIDI does not explicitly expose a channel value,
                # we assume channel 9 (MIDI channel 10) for drums, and 0 for others.
                "channel": 9 if instrument.is_drum else 0,
                "notes": notes_list
            })
        
        # Extract tempo changes
        tempo_times, tempos = midi_data.get_tempo_changes()
        tempo_changes = []
        for t, temp in zip(tempo_times, tempos):
            tempo_changes.append({
                "time": round(t, 3),
                "tempo": round(temp, 3)
            })
        
        # Extract time signature (meter) changes
        time_signatures = []
        for ts in midi_data.time_signature_changes:
            time_signatures.append({
                "time": round(ts.time, 3),
                "numerator": ts.numerator,
                "denominator": ts.denominator
            })
        
        response = {
            "instruments": instruments_data,
            "tempo_changes": tempo_changes,
            "time_signatures": time_signatures
        }
        
        return JSONResponse(response)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/generate-midi")
async def generate_midi(data: dict):
    """
    Accepts JSON with MIDI data and returns a base64-encoded MIDI file.
    
    Expected keys in the JSON (all are optional):
      - tempo_changes: list of objects { "time": float, "tempo": float }
      - time_signatures: list of objects { "time": float, "numerator": int, "denominator": int }
      - instruments: list of instruments, each with:
          - program: int (MIDI program number)
          - is_drum: bool
          - notes: list of note objects { "start": float, "duration": float, "pitch": int, "velocity": int }
    
    For backward compatibility, if only a flat "notes" array is provided, a default instrument (Acoustic Grand Piano) is used.
    """
    try:
        midi = pretty_midi.PrettyMIDI()
        
        # If tempo changes are provided, set them.
        # (Note: PrettyMIDI does not officially support setting multiple tempo changes,
        # so we use a hack by setting a private attribute.)
        if "tempo_changes" in data:
            tempo_changes = data["tempo_changes"]
            if tempo_changes:
                # Sort tempo changes by time to ensure correct ordering.
                tempo_changes.sort(key=lambda x: x["time"])
                times = [tc["time"] for tc in tempo_changes]
                tempos = [tc["tempo"] for tc in tempo_changes]
                midi._tempo_changes = (np.array(times), np.array(tempos))
        
        # Add time signature changes if provided.
        if "time_signatures" in data:
            for ts in data["time_signatures"]:
                time_sig = pretty_midi.containers.TimeSignature(
                    numerator=ts["numerator"],
                    denominator=ts["denominator"],
                    time=ts["time"]
                )
                midi.time_signature_changes.append(time_sig)
        
        # Add instruments and their notes.
        # The API supports a hierarchical structure (with "instruments") for richer MIDI content.
        if "instruments" in data:
            instruments_data = data["instruments"]
            for inst in instruments_data:
                # Create a new instrument.
                instrument = pretty_midi.Instrument(
                    program=inst.get("program", 0),
                    is_drum=inst.get("is_drum", False)
                )
                # Note: PrettyMIDI does not provide an API to explicitly set the MIDI channel.
                for note_data in inst.get("notes", []):
                    start_time = float(note_data["start"])
                    duration = float(note_data["duration"])
                    pitch = int(note_data["pitch"])
                    velocity = int(note_data["velocity"])
                    note = pretty_midi.Note(
                        velocity=velocity,
                        pitch=pitch,
                        start=start_time,
                        end=start_time + duration
                    )
                    instrument.notes.append(note)
                midi.instruments.append(instrument)
        elif "notes" in data:
            # Backward compatibility: if only a flat list of notes is provided,
            # add them to a default instrument.
            instrument = pretty_midi.Instrument(program=0)
            for note_data in data["notes"]:
                start_time = float(note_data["start"])
                duration = float(note_data["duration"])
                pitch = int(note_data["pitch"])
                velocity = int(note_data["velocity"])
                note = pretty_midi.Note(
                    velocity=velocity,
                    pitch=pitch,
                    start=start_time,
                    end=start_time + duration
                )
                instrument.notes.append(note)
            midi.instruments.append(instrument)
        
        # Write the MIDI data to an in-memory buffer and encode it as base64.
        buffer = io.BytesIO()
        midi.write(buffer)
        buffer.seek(0)
        midi_b64 = base64.b64encode(buffer.read()).decode("utf-8")
        
        return JSONResponse({"midi_base64": midi_b64})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
