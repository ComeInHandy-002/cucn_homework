package com.safety.admin.dataset;

import com.safety.admin.common.BusinessException;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.List;

@Service
public class DatasetService {

    private final DatasetRepository repository;
    private final Path uploadRoot;

    public DatasetService(DatasetRepository repository,
                          @Value("${app.train.repo-root}") String repoRoot) {
        this.repository = repository;
        this.uploadRoot = Path.of(repoRoot, "data", "admin_uploads");
    }

    public Dataset upload(String name, String note, MultipartFile file) {
        if (file == null || file.isEmpty()) {
            throw new BusinessException("上传文件不能为空");
        }
        try {
            Files.createDirectories(uploadRoot);
            String stored = System.currentTimeMillis() + "_" + file.getOriginalFilename();
            Path target = uploadRoot.resolve(stored).normalize();
            if (!target.startsWith(uploadRoot)) {
                throw new BusinessException("非法的存储路径");
            }
            file.transferTo(target.toFile());
            Dataset dataset = new Dataset();
            dataset.setName(name != null && !name.isBlank() ? name : file.getOriginalFilename());
            dataset.setOriginalFilename(file.getOriginalFilename());
            dataset.setStoredPath(target.toString());
            dataset.setSizeBytes(file.getSize());
            dataset.setSha256(sha256Of(target));
            dataset.setNote(note);
            return repository.save(dataset);
        } catch (IOException exc) {
            throw new BusinessException("文件保存失败：" + exc.getMessage());
        }
    }

    public List<Dataset> list() {
        return repository.findAll();
    }

    public Dataset detail(Long id) {
        return repository.findById(id).orElseThrow(() -> new BusinessException(404, "数据集不存在"));
    }

    public void delete(Long id) {
        Dataset dataset = detail(id);
        try {
            Files.deleteIfExists(Path.of(dataset.getStoredPath()));
        } catch (IOException exc) {
            // 磁盘文件删除失败不阻塞记录删除，但记录日志便于排查
        }
        repository.deleteById(id);
    }

    private String sha256Of(Path file) {
        try (InputStream in = Files.newInputStream(file)) {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) > 0) {
                digest.update(buffer, 0, read);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException exc) {
            return null;
        }
    }
}
