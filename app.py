from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn
import io
import pretty_midi

app = FastAPI(
    title="MIDI Converter API",
    description="Convert MIDI <-> JSON",
    version="1.0.0",
)

@app.post("/convert-midi")
async def convert_midi(file: UploadFile = File(...)):
    """
    Convert an uploaded MIDI file into a JSON structure describing note events.
    """
    # 1. Read file contents into memory
    midi_bytes = await file.read()
    
    # 2. Parse MIDI from bytes
    midi_data = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    
    # 3. Collect notes (start, duration, pitch, velocity)
    notes_list = []
    for instrument in midi_data.instruments:
        for note in instrument.notes:
            notes_list.append({
                "start": round(note.start, 3),
                "duration": round(note.end - note.start, 3),
                "pitch": note.pitch,
                "velocity": note.velocity
            })
    
    # 4. Return JSON response
    return JSONResponse({"notes": notes_list})


@app.post("/generate-midi")
async def generate_midi(data: dict):
    """
    Accept JSON with note events and return a generated MIDI file.
    The JSON structure should look like:
    {
      "notes": [
        {"start": 0.0, "duration": 0.236, "pitch": 60, "velocity": 100},
        ...
      ]
    }
    """
    notes = data.get("notes", [])
    
    # 1. Create a new MIDI object
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano
    
    # 2. Convert note data into pretty_midi.Note objects
    for n in notes:
        start_time = float(n["start"])
        duration = float(n["duration"])
        pitch = int(n["pitch"])
        velocity = int(n["velocity"])
        
        note = pretty_midi.Note(
            velocity=velocity,
            pitch=pitch,
            start=start_time,
            end=start_time + duration
        )
        instrument.notes.append(note)
    
    # 3. Add the instrument to the MIDI object
    midi.instruments.append(instrument)
    
    # 4. Write the MIDI to an in-memory buffer
    midi_buffer = io.BytesIO()
    midi.write(midi_buffer)
    midi_buffer.seek(0)
    
    # 5. Return MIDI file as a downloadable response
    headers = {
        "Content-Disposition": "attachment; filename=generated.mid"
    }
    return StreamingResponse(
        midi_buffer,
        media_type="audio/midi",
        headers=headers
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
