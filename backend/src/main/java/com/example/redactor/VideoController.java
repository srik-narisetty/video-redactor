package com.example.redactor;

import org.springframework.core.io.FileSystemResource;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "http://localhost:5173")
public class VideoController {
    private final Path workspace = Paths.get("work").toAbsolutePath();
    @GetMapping("/health") public Map<String,String> health() { return Map.of("status","ok"); }

    @PostMapping(value="/videos/redact", consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<?> redact(@RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue="true") boolean faces,
            @RequestParam(defaultValue="true") boolean plates) {
        if (file.isEmpty()) return ResponseEntity.badRequest().body(Map.of("error","Choose a video file"));
        String original = Optional.ofNullable(file.getOriginalFilename()).orElse("video.mp4");
        String extension = original.contains(".") ? original.substring(original.lastIndexOf('.')+1).toLowerCase(Locale.ROOT) : "";
        if (!Set.of("mp4","mov","avi","mkv","webm").contains(extension))
            return ResponseEntity.badRequest().body(Map.of("error","Supported formats: MP4, MOV, AVI, MKV, WEBM"));
        String id = UUID.randomUUID().toString();
        Path input = workspace.resolve("input").resolve(id+"."+extension);
        Path output = workspace.resolve("output").resolve(id+".mp4");
        try {
            Files.createDirectories(input.getParent());
            Files.createDirectories(output.getParent());
            file.transferTo(input);
            // backend/ directory is working directory for `mvn spring-boot:run`.
            Path processor = Paths.get("..").resolve("processor/redact.py").toAbsolutePath().normalize();
            String python = System.getenv().getOrDefault("PYTHON_BIN", "python");
            ProcessBuilder pb = new ProcessBuilder(python, processor.toString(), "--input", input.toString(),
                    "--output", output.toString(), "--faces", String.valueOf(faces), "--plates", String.valueOf(plates));
            pb.redirectErrorStream(true);
            Process process = pb.start();
            ByteArrayOutputStream logs = new ByteArrayOutputStream();
            Thread logThread = new Thread(() -> {
                try (InputStream stream = process.getInputStream()) { stream.transferTo(logs); }
                catch (IOException ignored) { }
            });
            logThread.start();
            boolean finished = process.waitFor(10, TimeUnit.MINUTES);
            if (!finished) { process.destroyForcibly(); logThread.join(2000); throw new IOException("Processing timed out after 10 minutes"); }
            logThread.join(2000);
            if (process.exitValue()!=0 || !Files.exists(output))
                throw new IOException("Video processing failed: " + logs.toString().substring(0, Math.min(1200,logs.size())));
            FileSystemResource resource = new FileSystemResource(output);
            return ResponseEntity.ok().contentType(MediaType.parseMediaType("video/mp4"))
                    .header(HttpHeaders.CONTENT_DISPOSITION,"attachment; filename=redacted-"+id+".mp4")
                    .contentLength(Files.size(output)).body(resource);
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of("error",e.getMessage()==null?"Processing failed":e.getMessage()));
        } finally {
            try { Files.deleteIfExists(input); } catch (IOException ignored) { }
        }
    }
}
