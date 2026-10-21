package com.safety.admin.modeltask;

import com.safety.admin.common.Result;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/** 模型在线训练与评估接口：创建训练任务 / 查询状态 / 列表 / 最新评估指标。 */
@RestController
@RequestMapping("/api/models")
public class ModelTrainController {

    private final ModelTrainService service;

    public ModelTrainController(ModelTrainService service) {
        this.service = service;
    }

    @PostMapping("/train")
    public Result<ModelTrainTask> train(@RequestBody(required = false) TrainRequest request) {
        String name = request == null ? null : request.name();
        String datasetTag = request == null ? null : request.datasetTag();
        return Result.ok(service.create(name, datasetTag));
    }

    @GetMapping("/train/{id}")
    public Result<ModelTrainTask> status(@PathVariable Long id) {
        return Result.ok(service.get(id));
    }

    @GetMapping("/train")
    public Result<List<ModelTrainTask>> list() {
        return Result.ok(service.list());
    }

    @GetMapping("/evaluation")
    public Result<ModelTrainTask> latestEvaluation() {
        return Result.ok(service.latestEvaluation());
    }

    public record TrainRequest(String name, String datasetTag) {
    }
}
