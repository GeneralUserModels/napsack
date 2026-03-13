from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import math
from PIL import Image, ImageDraw
import numpy as np
import av

from napsack.label.models import Aggregation, ImagePath


BUTTON_COLORS = {
    'left': 'red',
    'right': 'yellow',
    'middle': 'green'
}


def get_video_duration(video_path: Path) -> Optional[float]:
    try:
        with av.open(str(video_path)) as container:
            return container.duration / 1_000_000.0
    except Exception:
        return None


def split_video(video_path: Path, chunk_duration: int, out_dir: Path, start_index: int = 0) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = get_video_duration(video_path)
    if duration is None:
        raise RuntimeError("Could not get video duration")

    num_chunks = math.ceil(duration / float(chunk_duration))
    chunk_paths = []

    print(f"[Split] 1-minute chunking: Splitting {video_path.name} into {num_chunks} chunks of {chunk_duration}s each (total duration: {duration:.1f}s)")

    with av.open(str(video_path)) as input_container:
        video_stream = input_container.streams.video[0]
        fps = float(video_stream.average_rate)

        for i in range(num_chunks):
            start_s = i * chunk_duration
            end_s = min((i + 1) * chunk_duration, duration)
            out_path = out_dir / f"{start_index + i:03d}.mp4"

            input_container.seek(int(start_s * 1_000_000))

            with av.open(str(out_path), 'w', format='mp4') as output_container:
                out_stream = output_container.add_stream('libx264', rate=fps)
                out_stream.pix_fmt = 'yuv420p'
                out_stream.options = {'preset': 'veryfast', 'crf': '20'}

                for frame in input_container.decode(video_stream):
                    t = float(frame.pts * video_stream.time_base)
                    if t < start_s:
                        continue
                    if t >= end_s:
                        break
                    frame.pts = None
                    for packet in out_stream.encode(frame.reformat(format='yuv420p')):
                        output_container.mux(packet)

                for packet in out_stream.encode():
                    output_container.mux(packet)

            chunk_paths.append(out_path)

    return chunk_paths


def compute_max_size(image_paths: List[Path]) -> Tuple[int, int]:
    max_w, max_h = 0, 0

    for p in image_paths:
        try:
            with Image.open(p) as im:
                w, h = im.size
            max_w = max(max_w, w)
            max_h = max(max_h, h)
        except Exception:
            continue

    return (max_w, max_h) if max_w > 0 else (1920, 1080)


def scale_and_pad(img: Image.Image, target_w: int, target_h: int) -> Tuple[Image.Image, float, int, int]:
    orig_w, orig_h = img.size

    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    scaled = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    result = Image.new('RGB', (target_w, target_h), (0, 0, 0))

    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    result.paste(scaled, (x_offset, y_offset))

    return result, scale, x_offset, y_offset


def is_position_on_monitor(pos, monitor):
    """Check if a position is within the bounds of a monitor."""
    if not pos or len(pos) < 2 or not monitor:
        return False
    x, y = pos
    return (monitor['left'] <= x < monitor['left'] + monitor['width'] and
            monitor['top'] <= y < monitor['top'] + monitor['height'])


def screen_to_image_coords(screen_pos, monitor, scale, x_offset, y_offset):
    x, y = screen_pos
    img_x = (x - monitor['left']) * scale + x_offset
    img_y = (y - monitor['top']) * scale + y_offset
    return int(img_x), int(img_y)


class SyntheticEvent:
    """Synthetic event to represent cross-monitor cursor movement."""

    def __init__(self, cursor_position, monitor):
        self.cursor_position = cursor_position
        self.monitor = monitor
        self.is_mouse_event = False


def apply_pending_movement(agg: Aggregation, pending_movement: Optional[Tuple]) -> Aggregation:
    agg.events = pending_movement + agg.events

    return agg


def extract_pending_movement(agg: Aggregation) -> Optional[Tuple]:
    """
    Extract pending movement if cursor exits the current monitor.

    Args:
        agg: Current aggregation
    """
    if not agg.monitor or not agg.events:
        return []

    monitor = agg.monitor
    mpos_events = [e for e in agg.events if e.cursor_position and len(e.cursor_position) >= 2]

    if not mpos_events:
        return []

    pending_events = []
    next_monitor = None
    for i in range(len(mpos_events) - 1):
        next_pos = mpos_events[i + 1].cursor_position
        next_on_monitor = is_position_on_monitor(next_pos, monitor)

        if not next_on_monitor:
            if not next_monitor:
                pending_events.append(mpos_events[i + 1])
                next_monitor = mpos_events[i + 1].monitor
            elif next_monitor == mpos_events[i + 1].monitor:
                pending_events.append(mpos_events[i + 1])
            else:
                return pending_events
    return pending_events


def annotate_image(
    img: Image.Image,
    agg: Aggregation,
    scale: float = 1.0,
    x_offset: int = 0,
    y_offset: int = 0
) -> Image.Image:
    if not agg.monitor or not agg.events:
        return img

    draw = ImageDraw.Draw(img)
    monitor = agg.monitor

    movements = []
    prev_pos = None
    mpos_events = [e for e in agg.events if e.cursor_position and len(e.cursor_position) >= 2]

    for event in mpos_events:
        curr_pos = event.cursor_position

        if prev_pos and prev_pos != curr_pos:
            prev_on_monitor = is_position_on_monitor(prev_pos, monitor)
            curr_on_monitor = is_position_on_monitor(curr_pos, monitor)

            if prev_on_monitor and curr_on_monitor:
                movements.append({'start': prev_pos, 'end': curr_pos})

        prev_pos = curr_pos

    if len(movements) >= 1:
        drawn_indices = []
        for i, mov in enumerate(movements):
            was_drawn = draw_arrow(draw, img.size, mov['start'], mov['end'], monitor,
                                   scale * agg.scale_factor, x_offset, y_offset, draw_head=False, draw_start=(i == 0))
            if was_drawn:
                drawn_indices.append(i)

        if drawn_indices:
            last_idx = drawn_indices[-1]
            mov = movements[last_idx]
            draw_arrow(draw, img.size, mov['start'], mov['end'], monitor,
                       scale * agg.scale_factor, x_offset, y_offset, draw_head=True)

    clicks = [e for e in agg.events if e.is_mouse_event]
    for click in clicks:
        pos = click.cursor_position
        if not pos or len(pos) < 2:
            continue

        if not is_position_on_monitor(pos, monitor):
            continue

        img_x, img_y = screen_to_image_coords(pos, monitor, scale * agg.scale_factor, x_offset, y_offset)
        button = click.details.data.get('button', 'left').replace('Button.', '').lower()
        color = BUTTON_COLORS.get(button, 'yellow')
        radius = int(8 * scale)
        draw.ellipse(
            [(img_x - radius, img_y - radius), (img_x + radius, img_y + radius)],
            fill=color, outline='black', width=2
        )
    return img


def draw_arrow(draw, img_size, start_pos, end_pos, monitor, scale, x_offset, y_offset, draw_head=True, draw_start=False) -> bool:
    start_x, start_y = screen_to_image_coords(start_pos, monitor, scale, x_offset, y_offset)
    end_x, end_y = screen_to_image_coords(end_pos, monitor, scale, x_offset, y_offset)
    width, height = img_size
    marker_size = int(8 * scale)
    if draw_start:
        draw.ellipse(
            [(start_x - marker_size, start_y - marker_size),
             (start_x + marker_size, start_y + marker_size)],
            fill='blue', outline='black', width=2
        )

    line_width = max(1, int(3 * scale))
    draw.line([(start_x, start_y), (end_x, end_y)], fill='orange', width=line_width)

    if draw_head:
        arrow_length = int(25 * scale)
        dx, dy = end_x - start_x, end_y - start_y
        angle = np.arctan2(dy, dx)
        arrow_angle_rad = np.radians(40)
        x1 = end_x - arrow_length * np.cos(angle - arrow_angle_rad)
        y1 = end_y - arrow_length * np.sin(angle - arrow_angle_rad)
        x2 = end_x - arrow_length * np.cos(angle + arrow_angle_rad)
        y2 = end_y - arrow_length * np.sin(angle + arrow_angle_rad)
        draw.polygon([(end_x, end_y), (x1, y1), (x2, y2)], fill='orange', outline='darkorange')

    return True


def _encode_frames_to_video(frame_files: List[Path], output_path: Path, fps: int):
    """Encode a sorted list of image files to an mp4 using PyAV (libx264)."""
    if not frame_files:
        return

    with Image.open(frame_files[0]) as first:
        out_w = (first.width // 2) * 2
        out_h = (first.height // 2) * 2

    with av.open(str(output_path), 'w', format='mp4') as container:
        stream = container.add_stream('libx264', rate=fps)
        stream.width = out_w
        stream.height = out_h
        stream.pix_fmt = 'yuv420p'
        stream.options = {'preset': 'veryfast', 'crf': '20'}

        for frame_file in frame_files:
            with Image.open(frame_file) as img:
                img = img.convert('RGB')
                if img.width != out_w or img.height != out_h:
                    img = img.crop((0, 0, out_w, out_h))
                arr = np.array(img)
            av_frame = av.VideoFrame.from_ndarray(arr, format='rgb24')
            av_frame = av_frame.reformat(format='yuv420p')
            for packet in stream.encode(av_frame):
                container.mux(packet)

        for packet in stream.encode():
            container.mux(packet)


def create_video(
    image_paths: List[Path],
    output_path: Path,
    fps: int = 1,
    pad_to: Optional[Tuple[int, int]] = None,
    annotate: bool = False,
    aggregations: Optional[List[Aggregation]] = None,
    session_dir: Optional[Path] = None
):

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="video_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        pending_movement = []

        if aggregations is not None:
            for idx, agg in enumerate(aggregations):
                src = Path(agg.screenshot_path)
                if not src.exists():
                    src = session_dir / "screenshots" / agg.screenshot_path.name if session_dir else None
                dst = tmpdir_path / f"{idx:06d}.png"

                if annotate:
                    agg = apply_pending_movement(agg, pending_movement)

                    img_path = ImagePath(src, session_dir)
                    img = img_path.load()

                    if pad_to:
                        img, scale, x_off, y_off = scale_and_pad(img, pad_to[0], pad_to[1])
                    else:
                        scale, x_off, y_off = 1.0, 0, 0

                    img = annotate_image(img, agg, scale, x_off, y_off)
                    pending_movement = extract_pending_movement(agg)
                    img.save(dst)
                else:
                    with Image.open(src) as im:
                        img = im.convert('RGB')
                        if pad_to:
                            img, _, _, _ = scale_and_pad(img, pad_to[0], pad_to[1])
                        img.save(dst, format="PNG")
                    pending_movement = []
        else:
            for idx, img_path in enumerate(image_paths):
                src = Path(img_path)
                dst = tmpdir_path / f"{idx:06d}.png"
                with Image.open(src) as im:
                    img = im.convert('RGB')
                    if pad_to:
                        img, _, _, _ = scale_and_pad(img, pad_to[0], pad_to[1])
                    img.save(dst, format="PNG")

        _encode_frames_to_video(sorted(tmpdir_path.glob('*.png')), output_path, fps)
