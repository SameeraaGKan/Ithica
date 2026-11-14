"""Transcribe/ingest one FaZe video's transcript.
  python -m scripts.ingest_transcript --video-id dQw4w9WgXcQ --captions captions.vtt   # FaZe-provided or YouTube captions
  python -m scripts.ingest_transcript --video-id dQw4w9WgXcQ --audio clip.mp3          # Whisper if installed, else Gemini
Writes data/transcripts.json and (if MONGODB_URI) Atlas transcript_chunks with embeddings.
Atlas: add a vector index `transcript_vector` on transcript_chunks.embedding (768, cosine) + filter on video_id."""
import argparse
import asyncio
from pathlib import Path

from app.config import get_settings
from app.services import gemini, transcripts as T


async def main(a) -> None:
    if a.captions:
        segs = T.parse_captions(Path(a.captions).read_text(encoding="utf-8", errors="ignore"))
        how = "captions"
    else:
        audio = Path(a.audio)
        segs, how = T.whisper(audio), "whisper"
        if segs is None:
            segs, how = await T.gemini_transcribe(audio), "gemini"
    if not segs:
        raise SystemExit("no transcript produced")
    chunks = T.chunk(segs)
    vecs = await gemini.embed([c["text"] for c in chunks], timeout=60)
    T.save_local(a.video_id, chunks)
    s = get_settings()
    if s.has_mongo and vecs:
        from motor.motor_asyncio import AsyncIOMotorClient
        db = AsyncIOMotorClient(s.mongodb_uri)[s.mongodb_db]
        await db.transcript_chunks.delete_many({"video_id": a.video_id})
        await db.transcript_chunks.insert_many([{"video_id": a.video_id, **c, "embedding": v} for c, v in zip(chunks, vecs)])
    print(f"{a.video_id}: {len(segs)} segments via {how} -> {len(chunks)} chunks (embedded={bool(vecs)}, atlas={s.has_mongo and bool(vecs)})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video-id", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--captions")
    g.add_argument("--audio")
    asyncio.run(main(ap.parse_args()))
