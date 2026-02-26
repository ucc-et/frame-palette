import cv2
import csv
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from tqdm import tqdm

# ---- CONFIG ----
VIDEO_PATH = "C:\\Users\\ugurt\\Videos\\LordOfRings.mp4"
OUTPUT_CSV = "frame_colors.csv"

NUM_WORKERS = 8          # number of CPU workers
QUEUE_SIZE = 64          # buffer for decoded frames
# -------------------------


def worker(q, results_list):
    """
    Worker thread: takes (index, frame) from queue and computes average color.
    Appends result as (index, R, G, B) into results_list.
    """
    while True:
        item = q.get()
        if item is None:
            q.task_done()
            break

        index, frame = item

        # Fast average: NumPy vectorized
        avg = frame.mean(axis=(0, 1))  # B,G,R float
        b, g, r = avg
        results_list.append((index, int(r), int(g), int(b)))

        q.task_done()


def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Queue acts as frame buffer between decoder and workers
    q = Queue(maxsize=QUEUE_SIZE)

    # List to hold final results
    results = []

    # Start parallel workers
    pool = []
    for _ in range(NUM_WORKERS):
        executor = ThreadPoolExecutor(max_workers=1)
        fut = executor.submit(worker, q, results)
        pool.append((executor, fut))

    # Progress bar
    pbar = tqdm(total=total_frames, desc="Processing Frames", smoothing=0.1)

    # Read + enqueue frames
    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        q.put((frame_index, frame))
        frame_index += 1
        pbar.update(1)

    cap.release()
    pbar.close()

    # Tell workers to exit
    for _ in range(NUM_WORKERS):
        q.put(None)

    # Wait for queue to empty
    q.join()

    # Ensure all workers finished
    for executor, fut in pool:
        fut.result()
        executor.shutdown()

    # Sort results by frame index
    results.sort(key=lambda x: x[0])

    # Save to CSV
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["frame", "R", "G", "B"])
        writer.writerows(results)

    print(f"\nDone! Saved CSV to: {OUTPUT_CSV}")
    print(f"Total frames processed: {len(results)}")


if __name__ == "__main__":
    main()