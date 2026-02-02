# 前端上傳優化指南

## 概述

後端支持兩種上傳方式：
1. **完整文件上傳**：適用於小文件（<100MB）
2. **切片上傳**：適用於大文件（>100MB），減少內存占用，支持斷點續傳

## API 端點

### 1. 完整文件上傳（小文件）

#### 端點
```
POST /api/upload
```

#### 參數
- `file`: 文件（multipart/form-data）
- `provider`: "s3" 或 "oss"（可選，默認 "s3"）
- `bucket`: S3 bucket 名稱（可選）
- `region`: AWS 區域（可選）

#### 響應
```json
{
  "job_id": "abc12345",
  "status": "pending",
  "message": "File uploaded successfully. Conversion started.",
  "status_url": "/api/status/abc12345"
}
```

### 2. 切片上傳（大文件，推薦）

#### 端點 1：上傳切片
```
POST /api/upload/chunk
```

#### 參數
- `chunk`: 文件切片（multipart/form-data）
- `upload_id`: 上傳 ID（用於標識同一個文件的所有切片）
- `chunk_index`: 切片索引（從 0 開始）
- `total_chunks`: 總切片數
- `filename`: 原始文件名
- `chunk_size`: 切片大小（字節，可選）

#### 響應
```json
{
  "upload_id": "upload-123",
  "chunk_index": 0,
  "chunk_size": 5242880,
  "received_chunks": 1,
  "total_chunks": 10,
  "complete": false
}
```

#### 端點 2：完成上傳
```
POST /api/upload/complete
```

#### 參數
- `upload_id`: 上傳 ID
- `provider`: "s3" 或 "oss"（可選，默認 "s3"）
- `bucket`: S3 bucket 名稱（可選）
- `region`: AWS 區域（可選）

#### 響應
```json
{
  "job_id": "abc12345",
  "status": "pending",
  "message": "File uploaded and merged successfully. Conversion started.",
  "status_url": "/api/status/abc12345",
  "file_size": 52428800
}
```

#### 端點 3：查詢切片上傳狀態
```
GET /api/upload/chunk/status/{upload_id}
```

#### 響應
```json
{
  "upload_id": "upload-123",
  "received_chunks": 5,
  "total_chunks": 10,
  "progress": 50.0,
  "complete": false,
  "filename": "large-file.svs"
}
```

## 前端實現方案

### 方案 1：切片上傳（推薦，適用於大文件）

#### 完整實現（帶進度顯示和錯誤處理）

```javascript
class ChunkedFileUploader {
  constructor(apiUrl, chunkSize = 5 * 1024 * 1024) {
    this.apiUrl = apiUrl;
    this.chunkSize = chunkSize; // 5MB 默認切片大小
  }

  async uploadFile(file, onProgress, options = {}) {
    const {
      provider = 's3',
      bucket = '2026-demo',
      region = 'eu-west-2'
    } = options;

    // 生成上傳 ID
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // 計算切片數量
    const totalChunks = Math.ceil(file.size / this.chunkSize);
    
    console.log(`開始切片上傳: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB, ${totalChunks} 個切片)`);

    // 上傳所有切片
    const uploadPromises = [];
    for (let i = 0; i < totalChunks; i++) {
      const start = i * this.chunkSize;
      const end = Math.min(start + this.chunkSize, file.size);
      const chunk = file.slice(start, end);

      uploadPromises.push(
        this.uploadChunk(uploadId, i, totalChunks, chunk, file.name, onProgress)
      );
    }

    // 等待所有切片上傳完成
    try {
      await Promise.all(uploadPromises);
      console.log('所有切片上傳完成，開始合併...');

      // 完成上傳
      const result = await this.completeUpload(uploadId, provider, bucket, region);
      return result;
    } catch (error) {
      console.error('切片上傳失敗:', error);
      throw error;
    }
  }

  async uploadChunk(uploadId, chunkIndex, totalChunks, chunk, filename, onProgress) {
    const maxRetries = 3;
    let attempt = 0;

    while (attempt < maxRetries) {
      try {
        const formData = new FormData();
        formData.append('chunk', chunk);
        formData.append('upload_id', uploadId);
        formData.append('chunk_index', chunkIndex.toString());
        formData.append('total_chunks', totalChunks.toString());
        formData.append('filename', filename);
        formData.append('chunk_size', chunk.size.toString());

        const response = await fetch(`${this.apiUrl}/api/upload/chunk`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error(`Chunk upload failed: ${response.statusText}`);
        }

        const result = await response.json();
        
        // 更新總體進度
        if (onProgress) {
          const overallProgress = (result.received_chunks / result.total_chunks) * 100;
          onProgress(overallProgress, {
            chunkIndex: chunkIndex + 1,
            totalChunks: totalChunks,
            receivedChunks: result.received_chunks
          });
        }

        return result;
      } catch (error) {
        attempt++;
        if (attempt >= maxRetries) {
          throw new Error(`Failed to upload chunk ${chunkIndex} after ${maxRetries} attempts: ${error.message}`);
        }
        // 指數退避重試
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
        console.log(`重試上傳切片 ${chunkIndex + 1}/${totalChunks} (嘗試 ${attempt}/${maxRetries})`);
      }
    }
  }

  async completeUpload(uploadId, provider, bucket, region) {
    const formData = new FormData();
    formData.append('upload_id', uploadId);
    formData.append('provider', provider);
    formData.append('bucket', bucket);
    formData.append('region', region);

    const response = await fetch(`${this.apiUrl}/api/upload/complete`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`Complete upload failed: ${error.detail || response.statusText}`);
    }

    return await response.json();
  }

  async getChunkStatus(uploadId) {
    const response = await fetch(`${this.apiUrl}/api/upload/chunk/status/${uploadId}`);
    if (!response.ok) {
      throw new Error('Failed to get chunk status');
    }
    return await response.json();
  }
}

// 使用示例
const uploader = new ChunkedFileUploader('https://dzi-conversion-production.up.railway.app');

const fileInput = document.querySelector('input[type="file"]');
fileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  try {
    const result = await uploader.uploadFile(
      file,
      (progress, details) => {
        console.log(`上傳進度: ${progress.toFixed(1)}%`);
        console.log(`切片: ${details.chunkIndex}/${details.totalChunks}`);
        // 更新 UI 進度條
        updateProgressBar(progress);
      },
      {
        provider: 's3',
        bucket: '2026-demo',
        region: 'eu-west-2'
      }
    );

    console.log('上傳成功:', result);
    const jobId = result.job_id;
    
    // 開始輪詢轉換狀態
    pollConversionStatus(jobId);
  } catch (error) {
    console.error('上傳失敗:', error);
    alert('上傳失敗: ' + error.message);
  }
});
```

#### 並行上傳切片（更快）

```javascript
class ParallelChunkedUploader extends ChunkedFileUploader {
  constructor(apiUrl, chunkSize = 5 * 1024 * 1024, maxConcurrent = 3) {
    super(apiUrl, chunkSize);
    this.maxConcurrent = maxConcurrent; // 最大並行上傳數
  }

  async uploadFile(file, onProgress, options = {}) {
    const uploadId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const totalChunks = Math.ceil(file.size / this.chunkSize);

    console.log(`開始並行切片上傳: ${file.name} (${totalChunks} 個切片, 最多 ${this.maxConcurrent} 個並行)`);

    // 創建所有切片的上傳任務
    const chunks = [];
    for (let i = 0; i < totalChunks; i++) {
      const start = i * this.chunkSize;
      const end = Math.min(start + this.chunkSize, file.size);
      chunks.push({
        index: i,
        data: file.slice(start, end),
        filename: file.name
      });
    }

    // 並行上傳（控制並發數）
    const uploadTasks = [];
    for (let i = 0; i < chunks.length; i += this.maxConcurrent) {
      const batch = chunks.slice(i, i + this.maxConcurrent);
      const batchPromises = batch.map(chunk =>
        this.uploadChunk(uploadId, chunk.index, totalChunks, chunk.data, chunk.filename, onProgress)
      );
      uploadTasks.push(Promise.all(batchPromises));
    }

    // 等待所有批次完成
    await Promise.all(uploadTasks);

    // 完成上傳
    return await this.completeUpload(uploadId, options.provider, options.bucket, options.region);
  }
}
```

### 方案 2：完整文件上傳（小文件，簡單快速）

#### 基本實現（小文件）
```javascript
async function uploadFile(file, onProgress) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('provider', 's3');
  formData.append('bucket', '2026-demo');
  formData.append('region', 'eu-west-2');

  const response = await fetch('https://dzi-conversion-production.up.railway.app/api/upload', {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }

  return await response.json();
}
```

#### 優化實現（大文件，帶進度顯示）
```javascript
async function uploadFileWithProgress(file, onProgress) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('provider', 's3');
  formData.append('bucket', '2026-demo');
  formData.append('region', 'eu-west-2');

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // 上傳進度
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    // 完成
    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        try {
          const result = JSON.parse(xhr.responseText);
          resolve(result);
        } catch (e) {
          reject(new Error('Invalid response'));
        }
      } else {
        reject(new Error(`Upload failed: ${xhr.statusText}`));
      }
    });

    // 錯誤
    xhr.addEventListener('error', () => {
      reject(new Error('Network error'));
    });

    // 開始上傳
    xhr.open('POST', 'https://dzi-conversion-production.up.railway.app/api/upload');
    xhr.send(formData);
  });
}

// 使用示例
const fileInput = document.querySelector('input[type="file"]');
fileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  try {
    const result = await uploadFileWithProgress(file, (progress) => {
      console.log(`Upload progress: ${progress.toFixed(1)}%`);
      // 更新 UI 進度條
      updateProgressBar(progress);
    });

    console.log('Upload successful:', result);
    const jobId = result.job_id;
    
    // 開始輪詢狀態
    pollStatus(jobId);
  } catch (error) {
    console.error('Upload failed:', error);
  }
});
```

### 方案 2：使用 Axios（推薦，更簡潔）

```javascript
import axios from 'axios';

async function uploadFile(file, onProgress) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('provider', 's3');
  formData.append('bucket', '2026-demo');
  formData.append('region', 'eu-west-2');

  const response = await axios.post(
    'https://dzi-conversion-production.up.railway.app/api/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
      timeout: 600000, // 10 分鐘超時（大文件需要）
    }
  );

  return response.data;
}

// 使用示例
const handleFileUpload = async (file) => {
  try {
    const result = await uploadFile(file, (progress) => {
      console.log(`Upload: ${progress}%`);
      // 更新進度條
    });

    console.log('Upload successful:', result);
    return result.job_id;
  } catch (error) {
    if (error.code === 'ECONNABORTED') {
      console.error('Upload timeout');
    } else {
      console.error('Upload error:', error);
    }
    throw error;
  }
};
```

### 方案 3：React 組件示例（切片上傳）

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function ChunkedFileUploader() {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);
  const [chunkInfo, setChunkInfo] = useState(null);

  const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB
  const MAX_CONCURRENT = 3; // 最多 3 個並行上傳
  const BASE_URL = 'https://dzi-conversion-production.up.railway.app';

  const uploadChunk = async (uploadId, chunkIndex, totalChunks, chunk, filename) => {
    const formData = new FormData();
    formData.append('chunk', chunk);
    formData.append('upload_id', uploadId);
    formData.append('chunk_index', chunkIndex.toString());
    formData.append('total_chunks', totalChunks.toString());
    formData.append('filename', filename);
    formData.append('chunk_size', chunk.size.toString());

    const response = await axios.post(`${BASE_URL}/api/upload/chunk`, formData, {
      timeout: 60000, // 60 秒超時
    });

    return response.data;
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 驗證文件類型
    const allowedTypes = ['.svs', '.tiff', '.tif', '.ndpi', '.mrxs', '.png', '.jpg', '.jpeg'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(fileExt)) {
      alert(`不支持的文件格式: ${fileExt}`);
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      // 生成上傳 ID
      const uploadId = `upload-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

      console.log(`開始上傳: ${file.name} (${totalChunks} 個切片)`);
      setChunkInfo({ current: 0, total: totalChunks });

      // 創建所有切片
      const chunks = [];
      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        chunks.push({
          index: i,
          data: file.slice(start, end),
        });
      }

      // 並行上傳（控制並發數）
      const uploadPromises = [];
      for (let i = 0; i < chunks.length; i += MAX_CONCURRENT) {
        const batch = chunks.slice(i, i + MAX_CONCURRENT);
        const batchPromises = batch.map(async (chunk) => {
          const result = await uploadChunk(uploadId, chunk.index, totalChunks, chunk.data, file.name);
          
          // 更新進度
          const progress = ((result.received_chunks / totalChunks) * 100);
          setUploadProgress(progress);
          setChunkInfo({ current: result.received_chunks, total: totalChunks });
          
          return result;
        });
        uploadPromises.push(Promise.all(batchPromises));
      }

      // 等待所有切片上傳完成
      await Promise.all(uploadPromises);

      // 完成上傳
      const formData = new FormData();
      formData.append('upload_id', uploadId);
      formData.append('provider', 's3');
      formData.append('bucket', '2026-demo');
      formData.append('region', 'eu-west-2');

      const completeResponse = await axios.post(`${BASE_URL}/api/upload/complete`, formData);
      const result = completeResponse.data;

      setJobId(result.job_id);
      setIsUploading(false);
      setUploadProgress(100);

      // 開始輪詢狀態
      pollStatus(result.job_id);
    } catch (error) {
      console.error('上傳失敗:', error);
      setIsUploading(false);
      alert('上傳失敗: ' + (error.response?.data?.detail || error.message));
    }
  };

  const pollStatus = (jobId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(`${BASE_URL}/api/status/${jobId}`);
        const status = response.data;
        setStatus(status);

        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval);
        }
      } catch (error) {
        console.error('狀態查詢失敗:', error);
      }
    }, 3000);
  };

  return (
    <div>
      <input
        type="file"
        onChange={handleFileChange}
        accept=".svs,.tiff,.tif,.ndpi,.mrxs,.png,.jpg,.jpeg"
        disabled={isUploading}
      />
      
      {isUploading && (
        <div>
          <p>上傳進度: {uploadProgress.toFixed(1)}%</p>
          {chunkInfo && (
            <p>切片: {chunkInfo.current}/{chunkInfo.total}</p>
          )}
          <progress value={uploadProgress} max="100" />
        </div>
      )}

      {status && (
        <div>
          <p>狀態: {status.status}</p>
          <p>進度: {status.progress}%</p>
          <p>{status.message}</p>
        </div>
      )}

      {status?.status === 'completed' && (
        <div>
          <p>✅ 轉換完成！</p>
          <a href={status.dzi_url} target="_blank" rel="noopener noreferrer">
            查看 DZI
          </a>
        </div>
      )}
    </div>
  );
}

export default ChunkedFileUploader;
```

### 方案 4：完整文件上傳（小文件，簡單快速）

```jsx
import React, { useState } from 'react';
import axios from 'axios';

function FileUploader() {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // 驗證文件類型
    const allowedTypes = ['.svs', '.tiff', '.tif', '.ndpi', '.mrxs', '.png', '.jpg', '.jpeg'];
    const fileExt = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowedTypes.includes(fileExt)) {
      alert(`不支持的文件格式: ${fileExt}`);
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('provider', 's3');
      formData.append('bucket', '2026-demo');
      formData.append('region', 'eu-west-2');

      const response = await axios.post(
        'https://dzi-conversion-production.up.railway.app/api/upload',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              const percentCompleted = Math.round(
                (progressEvent.loaded * 100) / progressEvent.total
              );
              setUploadProgress(percentCompleted);
            }
          },
          timeout: 600000, // 10 分鐘
        }
      );

      const result = response.data;
      setJobId(result.job_id);
      setIsUploading(false);
      
      // 開始輪詢狀態
      pollStatus(result.job_id);
    } catch (error) {
      console.error('Upload failed:', error);
      setIsUploading(false);
      alert('上傳失敗: ' + (error.message || 'Unknown error'));
    }
  };

  const pollStatus = async (jobId) => {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(
          `https://dzi-conversion-production.up.railway.app/api/status/${jobId}`
        );
        const status = response.data;
        setStatus(status);

        if (status.status === 'completed') {
          clearInterval(interval);
          alert('轉換完成！');
          console.log('DZI URL:', status.dzi_url);
          console.log('Thumbnail URL:', status.thumbnail_url);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          alert('轉換失敗: ' + status.message);
        }
      } catch (error) {
        console.error('Status check failed:', error);
      }
    }, 3000); // 每 3 秒查詢一次
  };

  return (
    <div>
      <input
        type="file"
        onChange={handleFileChange}
        accept=".svs,.tiff,.tif,.ndpi,.mrxs,.png,.jpg,.jpeg"
        disabled={isUploading}
      />
      
      {isUploading && (
        <div>
          <p>上傳進度: {uploadProgress}%</p>
          <progress value={uploadProgress} max="100" />
        </div>
      )}

      {status && (
        <div>
          <p>狀態: {status.status}</p>
          <p>進度: {status.progress}%</p>
          <p>{status.message}</p>
        </div>
      )}

      {status?.status === 'completed' && (
        <div>
          <p>✅ 轉換完成！</p>
          <a href={status.dzi_url} target="_blank" rel="noopener noreferrer">
            查看 DZI
          </a>
        </div>
      )}
    </div>
  );
}

export default FileUploader;
```

### 方案 4：Vue 3 組件示例

```vue
<template>
  <div>
    <input
      type="file"
      @change="handleFileChange"
      accept=".svs,.tiff,.tif,.ndpi,.mrxs,.png,.jpg,.jpeg"
      :disabled="isUploading"
    />
    
    <div v-if="isUploading">
      <p>上傳進度: {{ uploadProgress }}%</p>
      <progress :value="uploadProgress" max="100" />
    </div>

    <div v-if="status">
      <p>狀態: {{ status.status }}</p>
      <p>進度: {{ status.progress }}%</p>
      <p>{{ status.message }}</p>
    </div>

    <div v-if="status?.status === 'completed'">
      <p>✅ 轉換完成！</p>
      <a :href="status.dzi_url" target="_blank">查看 DZI</a>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import axios from 'axios';

const uploadProgress = ref(0);
const isUploading = ref(false);
const jobId = ref(null);
const status = ref(null);

const BASE_URL = 'https://dzi-conversion-production.up.railway.app';

const handleFileChange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  isUploading.value = true;
  uploadProgress.value = 0;

  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('provider', 's3');
    formData.append('bucket', '2026-demo');
    formData.append('region', 'eu-west-2');

    const response = await axios.post(
      `${BASE_URL}/api/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            uploadProgress.value = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
          }
        },
        timeout: 600000,
      }
    );

    jobId.value = response.data.job_id;
    isUploading.value = false;
    pollStatus(response.data.job_id);
  } catch (error) {
    console.error('Upload failed:', error);
    isUploading.value = false;
    alert('上傳失敗: ' + (error.message || 'Unknown error'));
  }
};

const pollStatus = (jobId) => {
  const interval = setInterval(async () => {
    try {
      const response = await axios.get(`${BASE_URL}/api/status/${jobId}`);
      status.value = response.data;

      if (status.value.status === 'completed' || status.value.status === 'failed') {
        clearInterval(interval);
      }
    } catch (error) {
      console.error('Status check failed:', error);
    }
  }, 3000);
};
</script>
```

## 重要注意事項

### 1. 超時設置
大文件（>100MB）上傳需要較長時間，確保設置足夠的超時時間：
- **Axios**: `timeout: 600000` (10 分鐘)
- **Fetch**: 使用 `AbortController` 手動控制

### 2. 進度顯示
使用 `XMLHttpRequest` 或 Axios 的 `onUploadProgress` 來顯示上傳進度。

### 3. 錯誤處理
- 網絡錯誤：顯示友好提示，允許重試
- 超時錯誤：提示用戶文件可能太大，建議檢查網絡
- 文件格式錯誤：在選擇文件時就驗證

### 4. 文件大小限制
雖然後端沒有硬性限制，但建議：
- 前端提示：大文件（>100MB）可能需要較長時間
- 顯示文件大小
- 對於超大文件（>500MB），考慮警告用戶

### 5. 狀態輪詢
上傳完成後，開始輪詢 `/api/status/{job_id}`：
- 初始間隔：3 秒
- 如果長時間無變化，可以逐漸增加間隔
- 顯示進度百分比和狀態消息

## 完整示例：帶錯誤處理和重試

```javascript
class FileUploader {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
    this.maxRetries = 3;
  }

  async upload(file, onProgress, onStatusUpdate) {
    let lastError;
    
    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      try {
        const result = await this.uploadAttempt(file, onProgress);
        
        // 開始輪詢狀態
        this.pollStatus(result.job_id, onStatusUpdate);
        
        return result;
      } catch (error) {
        lastError = error;
        if (attempt < this.maxRetries - 1) {
          const delay = Math.pow(2, attempt) * 1000; // 指數退避
          console.log(`Upload failed, retrying in ${delay}ms...`);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
    
    throw lastError;
  }

  async uploadAttempt(file, onProgress) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('provider', 's3');
    formData.append('bucket', '2026-demo');
    formData.append('region', 'eu-west-2');

    const response = await axios.post(
      `${this.apiUrl}/api/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (onProgress && progressEvent.total) {
            const percent = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(percent);
          }
        },
        timeout: 600000,
      }
    );

    return response.data;
  }

  async pollStatus(jobId, onStatusUpdate) {
    const interval = setInterval(async () => {
      try {
        const response = await axios.get(
          `${this.apiUrl}/api/status/${jobId}`
        );
        const status = response.data;
        
        if (onStatusUpdate) {
          onStatusUpdate(status);
        }

        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(interval);
        }
      } catch (error) {
        console.error('Status check failed:', error);
      }
    }, 3000);
  }
}

// 使用
const uploader = new FileUploader('https://dzi-conversion-production.up.railway.app');

uploader.upload(
  file,
  (progress) => console.log(`Upload: ${progress}%`),
  (status) => console.log(`Status: ${status.status}, Progress: ${status.progress}%`)
);
```

## 選擇上傳方式

### 小文件（<100MB）
- 使用 **完整文件上傳** (`/api/upload`)
- 簡單快速，無需切片處理

### 大文件（>100MB）
- 使用 **切片上傳** (`/api/upload/chunk` + `/api/upload/complete`)
- 減少內存占用
- 支持斷點續傳（可以實現）
- 更好的進度顯示

## 切片大小建議

- **5MB**：平衡性能和內存（推薦）
- **10MB**：更快，但需要更多內存
- **2MB**：更安全，適合內存受限環境

## 並行上傳建議

- **3-5 個並行**：平衡速度和穩定性（推薦）
- **更多並行**：可能導致網絡擁塞
- **順序上傳**：最穩定，但較慢

## 總結

現在後端支持兩種上傳方式：

1. ✅ **完整文件上傳**：適用於小文件，簡單快速
2. ✅ **切片上傳**：適用於大文件，減少內存占用，支持更好的進度顯示

主要優化點：
- 根據文件大小選擇合適的上傳方式
- 顯示上傳進度條（切片進度和總體進度）
- 設置合理的超時時間
- 實現錯誤處理和重試
- 狀態輪詢顯示轉換進度
- 並行上傳切片以提高速度
