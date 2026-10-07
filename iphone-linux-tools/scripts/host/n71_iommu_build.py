"""Bind the opt-in PCI IOMMU module to its qualified source and kernel Image."""
import hashlib
import json
import re
import struct
import zlib
import profile_image


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evidence(root, filename):
    path = root / 'docs/evidence' / filename
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 256 * 1024,
            'Qualified IOMMU evidence missing or invalid')
    return json.loads(path.read_text())


def qualified(root, *, release):
    proof = evidence(root, 'n71-dma-topology-qualification.json')
    build = proof['kernel_build']
    require(type(proof.get('format')) is int and proof['format'] == 1
            and build['kernel_exit'] == 0 and type(build['kernel_exit']) is int
            and build['loaded'] is False and build['private_wrapper'] is False
            and all(build[key] is True for key in ('production_module_inputs_identical',
                    'baseline_preserved', 'original_tracked_changes_preserved')), 'Exact qualified IOMMU build required')
    audit = proof['primary_source_audit']
    require(audit['source_commit'] == build['source_commit'] == '958481f87fee0949ff6a9a4af77f7eb6dac8a149'
            and audit['tracked_patch_sha256'] == build['original_tracked_patch_sha256']
            == '6e1fccc1c936ee94c3f921ebe75e6dda4670c647f16b6c864df5475e20764657'
            and audit['vmlinux_symbol_binding'] == {'pci_for_each_dma_alias': 'T', 'pci_real_dma_dev': 'W'}
            and audit['arm64_real_dma_override_files'] == []
            and audit['exported_group_apis'] == ['iommu_group_get', 'iommu_group_put', 'iommu_group_id']
            and audit['unexported_alias_helpers'] == ['pci_for_each_dma_alias', 'pci_real_dma_dev']
            and build['exported_group_apis_present'] is True
            and build['unexported_alias_helpers_not_referenced'] is True,
            'Qualified public DMA topology premises required')
    require(release == '7.2.0-iphone6s-dart-serdev-power2'
            and build['vermagic'] == release + ' SMP preempt mod_unload aarch64'
            and type(build['module_bytes']) is int and 64 <= build['module_bytes'] <= 256 * 1024
            and isinstance(build['module_sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', build['module_sha256']),
            'Qualified IOMMU module record differs')
    return build


def image_record(root, *, release):
    qualified_build = qualified(root, release=release)
    kernel = evidence(root, 'kernel-n71-binding-build.json')
    build = kernel['build']
    outputs = build['outputs']
    baseline = qualified_build['baseline_sha256']
    require(type(kernel.get('format')) is int and kernel['format'] == 1
            and kernel['status'] == 'compiled_verified' and type(build['exit_code']) is int
            and build['exit_code'] == 0 and build['full_image_linked'] is True
            and build['vmlinux_modpost_verified'] is True
            and kernel['source']['commit'] == qualified_build['source_commit']
            and build['kernel_release'] == release
            and build['vmlinux_symvers_sha256'] == baseline['vmlinux.symvers']
            and outputs['config']['sha256'] == baseline['.config']
            and outputs['Image']['sha256'] == baseline['arch/arm64/boot/Image'],
            'Kernel and IOMMU qualification differ')
    require(all(type(outputs[name]['bytes']) is int and 64 <= outputs[name]['bytes'] <= profile_image.MAX_IMAGE_BYTES
                and isinstance(outputs[name]['sha256'], str)
                and re.fullmatch(r'[0-9a-f]{64}', outputs[name]['sha256']) for name in ('Image', 'Image.gz')),
            'Qualified Image record differs')
    return outputs


def kernel_image(root, raw, *, release):
    outputs = image_record(root, release=release)
    require(len(raw) == outputs['Image.gz']['bytes']
            and hashlib.sha256(raw).hexdigest() == outputs['Image.gz']['sha256'],
            'Selected compressed kernel differs')
    try:
        decoder = zlib.decompressobj(31)
        image = decoder.decompress(raw, profile_image.MAX_IMAGE_BYTES + 1)
    except zlib.error as error:
        raise ValueError('Qualified kernel gzip required') from error
    require(len(image) <= profile_image.MAX_IMAGE_BYTES and decoder.eof
            and not decoder.unused_data and not decoder.unconsumed_tail,
            'Kernel must contain one complete bounded gzip stream')
    require(len(image) == outputs['Image']['bytes']
            and hashlib.sha256(image).hexdigest() == outputs['Image']['sha256'],
            'Compressed kernel does not contain the qualified Image')
    return outputs['Image']['sha256']


def payload_image(root, profile, metadata, *, prefix_bytes, release):
    require(type(prefix_bytes) is int and 0 <= prefix_bytes <= 2 * 1024 * 1024,
            'Validated payload prefix required')
    payload, initramfs = profile['payload'], profile['initramfs']
    size, tail = payload.stat().st_size, initramfs.stat().st_size
    require(0 < tail < size <= profile_image.MAX_IMAGE_BYTES, 'Bounded payload and initramfs required')
    with initramfs.open('rb') as stream:
        suffix = stream.read(tail + 1)
    require(len(suffix) == tail, 'Selected initramfs size changed')
    with payload.open('rb') as stream:
        stream.seek(prefix_bytes)
        header = stream.read(8)
        require(len(header) == 8, 'Complete payload FDT header required')
        magic, total = struct.unpack('>II', header)
        require(magic == 0xd00dfeed and 40 <= total <= 4 * 1024 * 1024,
                'Payload FDT framing differs')
        dtb = header + stream.read(total - 8)
        require(len(dtb) == total and hashlib.sha256(dtb).hexdigest() == metadata.get('dtb_sha256'),
                'Payload FDT differs from provenance')
        length = size - prefix_bytes - total - tail
        require(64 <= length <= profile_image.MAX_IMAGE_BYTES, 'Payload kernel range differs')
        raw = stream.read(length)
        require(len(raw) == length and stream.read(tail + 1) == suffix,
                'Payload kernel/initramfs boundary differs')
    return kernel_image(root, raw, release=release)
