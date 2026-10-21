package com.safety.admin.dataset;

import com.safety.admin.common.Result;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

/** 数据集管理接口：上传 / 列表 / 详情 / 删除。 */
@RestController
@RequestMapping("/api/datasets")
public class DatasetController {

    private final DatasetService service;

    public DatasetController(DatasetService service) {
        this.service = service;
    }

    @PostMapping
    public Result<Dataset> upload(@RequestParam("file") MultipartFile file,
                                  @RequestParam(value = "name", required = false) String name,
                                  @RequestParam(value = "note", required = false) String note) {
        return Result.ok(service.upload(name, note, file));
    }

    @GetMapping
    public Result<List<Dataset>> list() {
        return Result.ok(service.list());
    }

    @GetMapping("/{id}")
    public Result<Dataset> detail(@PathVariable Long id) {
        return Result.ok(service.detail(id));
    }

    @DeleteMapping("/{id}")
    public Result<Void> delete(@PathVariable Long id) {
        service.delete(id);
        return Result.ok();
    }
}
