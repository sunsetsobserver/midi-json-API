import base64
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
async def convert_midi(data: dict):
    """
    Accepts JSON with base64-encoded MIDI and returns extracted note data.
    """
    midi_b64 = data.get("midi_base64", None)
    if not midi_b64:
        return JSONResponse({"error": "No base64 MIDI provided."}, status_code=400)
    
    try:
        # Decode the base64 MIDI string into raw bytes
        midi_bytes = base64.b64decode(midi_b64)
        # Parse the MIDI data
        midi_data = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
        
        # Extract note information
        notes_list = []
        for instrument in midi_data.instruments:
            for note in instrument.notes:
                notes_list.append({
                    "start": round(note.start, 3),
                    "duration": round(note.end - note.start, 3),
                    "pitch": note.pitch,
                    "velocity": note.velocity
                })
        
        return JSONResponse({"notes": notes_list})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/generate-midi")
async def generate_midi(data: dict):
    """
    Accepts JSON with note events and returns a base64-encoded MIDI file.
    """
    notes = data.get("notes", [])

    # Create a new MIDI object
    midi = pretty_midi.PrettyMIDI()
    instrument = pretty_midi.Instrument(program=0)  # Acoustic Grand Piano
    
    # Convert note data into MIDI notes
    for note_data in notes:
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
    
    # Write MIDI to in-memory buffer
    buffer = io.BytesIO()
    midi.write(buffer)
    buffer.seek(0)
    
    # Convert MIDI to base64 string
    midi_b64 = base64.b64encode(buffer.read()).decode("utf-8")
    
    return JSONResponse({"midi_base64": midi_b64})
   
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

