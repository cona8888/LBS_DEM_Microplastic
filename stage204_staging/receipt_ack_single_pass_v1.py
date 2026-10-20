"""One receipt-existence decision per entry, with the original strict verifier.

No trajectory, contact model, checkpoint, receipt, or scientific gate changes.
Receipt publication is exclusive and immutable. An absent receipt stays pending
for this invocation; a present receipt is verified with its predecessor hash.
"""


def acknowledged(api, policy, design_path, design, pending):
    left = []
    for entry in pending:
        paths = entry['paths']
        if not paths['receipt'].exists():
            left.append(entry)
            continue
        receipt = api.read(paths['receipt'])
        if receipt['status'] != 'independently_verified':
            raise RuntimeError('independent segment audit rejected ' + str(paths['raw']))
        parent_path = entry.get('previous_receipt_path')
        previous_sha = None if parent_path is None else api.sha(parent_path)
        policy.verify_receipt(
            paths, entry['case'], entry['index'], api.sha(design_path),
            design['audit_source_sha256'], entry['before_sha'], previous_sha,
        )
    return left
