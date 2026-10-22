def build_batches(all_panels, batch_size, global_prompt):
    """Chia các panel liên tiếp thành batch và tạo prompt từ lời thoại đã OCR."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batches = []
    for start in range(0, len(all_panels), batch_size):
        subset = all_panels[start:start + batch_size]
        batch = {'id': f'batch_{len(batches)+1:04d}', 'context': '', 'status': 'needs_review',
                 'panel_ids': [p['id'] for p in subset]}
        lines = [global_prompt, '', 'Batch context: (optional; not provided)', '',
                 'Speakers are unknown. Infer from images and context; attribution may be uncertain.']
        for i, panel in enumerate(subset, 1):
            lines.append(f'\nImage {i}: {panel["image"]}')
            if not panel['texts']:
                lines.append('No text detected; verify during review.')
            for text in panel['texts']:
                lines.append(f'- {text["content"] or "[OCR empty: review required]"}')
        batch['prompt'] = '\n'.join(lines)
        batches.append(batch)
    return batches
