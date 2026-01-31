# S3 Bucket Policy 配置指南

## 您提供的策略

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadWrite",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject",
                "s3:PutObject"
            ],
            "Resource": "arn:aws:s3:::2026-demo/*"
        }
    ]
}
```

## 如何应用这个策略

### 步骤 1：登录 AWS 控制台

1. 访问 [AWS S3 控制台](https://console.aws.amazon.com/s3/)
2. 找到您的 bucket：`2026-demo`
3. 点击 bucket 名称进入详情页

### 步骤 2：应用 Bucket Policy

1. 点击 **"Permissions"**（权限）标签
2. 滚动到 **"Bucket policy"** 部分
3. 点击 **"Edit"**（编辑）
4. 粘贴以下**改进后的策略**（见下方）
5. 点击 **"Save changes"**

## 改进后的策略（推荐）

您的策略基本正确，但建议添加 `s3:PutObjectAcl` 权限，以便设置文件的访问控制：

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "PublicReadWrite",
            "Effect": "Allow",
            "Principal": "*",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:PutObjectAcl"
            ],
            "Resource": "arn:aws:s3:::2026-demo/*"
        },
        {
            "Sid": "PublicListBucket",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::2026-demo"
        }
    ]
}
```

### 改进说明：

1. **添加 `s3:PutObjectAcl`**：允许设置文件的 ACL（访问控制列表）
2. **添加 `s3:ListBucket`**：允许列出 bucket 内容（用于调试和验证）

## 重要注意事项

### ⚠️ 安全警告

这个策略允许**任何人**（Principal: "*"）对您的 bucket 进行读写操作。这意味着：

- ✅ 任何人都可以上传文件
- ✅ 任何人都可以下载文件
- ❌ 任何人都可以删除文件（如果添加了 DeleteObject）

**建议：**
- 如果这是测试环境，可以使用
- 如果是生产环境，建议：
  1. 移除 `Principal: "*"`，改为特定的 IAM 用户或角色
  2. 或者使用 IAM policy 而不是 bucket policy

### 两种策略的区别

| 类型 | 应用位置 | 作用范围 | 推荐场景 |
|------|----------|----------|----------|
| **Bucket Policy** | S3 Bucket | 影响所有访问该 bucket 的用户 | 公共访问、跨账户访问 |
| **IAM Policy** | IAM 用户/角色 | 只影响特定 IAM 用户 | 特定用户权限控制 |

## 如果仍然遇到 AccessDenied

即使设置了 bucket policy，如果仍然看到 `AccessDenied` 错误，可能的原因：

### 1. Block Public Access 设置

S3 bucket 可能启用了 "Block Public Access"（阻止公共访问），这会覆盖 bucket policy。

**解决方法：**
1. 在 S3 bucket 的 **"Permissions"** 标签
2. 找到 **"Block public access (bucket settings)"**
3. 点击 **"Edit"**
4. **取消勾选**以下选项（如果您的 bucket 需要公共访问）：
   - ☐ Block all public access
   - ☐ Block public access to buckets and objects granted through new access control lists (ACLs)
   - ☐ Block public access to buckets and objects granted through any access control lists (ACLs)
   - ☐ Block public access to buckets and objects granted through new public bucket or access point policies
   - ☐ Block public and cross-account access to buckets and objects through any public bucket or access point policies
5. 点击 **"Save changes"**
6. 确认更改

### 2. CORS 配置（如果需要从浏览器上传）

如果从浏览器直接上传，可能需要配置 CORS：

```json
[
    {
        "AllowedHeaders": [
            "*"
        ],
        "AllowedMethods": [
            "GET",
            "PUT",
            "POST",
            "DELETE",
            "HEAD"
        ],
        "AllowedOrigins": [
            "*"
        ],
        "ExposeHeaders": [
            "ETag"
        ],
        "MaxAgeSeconds": 3000
    }
]
```

**应用 CORS：**
1. S3 bucket → **"Permissions"** 标签
2. 滚动到 **"Cross-origin resource sharing (CORS)"**
3. 点击 **"Edit"**
4. 粘贴上面的 CORS 配置
5. 点击 **"Save changes"**

### 3. 同时需要 IAM Policy

即使 bucket policy 允许公共访问，如果使用 IAM 凭证，**仍然需要 IAM policy**。

**原因：**
- Bucket policy 控制 bucket 级别的访问
- IAM policy 控制 IAM 用户的权限
- 两者都需要正确配置

**建议配置：**

**IAM Policy（附加到 IAM 用户）：**
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::2026-demo",
                "arn:aws:s3:::2026-demo/*"
            ]
        }
    ]
}
```

## 完整配置检查清单

- [ ] Bucket Policy 已应用（允许 PutObject）
- [ ] Block Public Access 已禁用（如果需要公共访问）
- [ ] IAM Policy 已附加到 IAM 用户（如果使用 IAM 凭证）
- [ ] IAM 用户有访问密钥
- [ ] Railway 环境变量已设置（AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）
- [ ] Bucket 名称和 Region 正确

## 验证配置

### 使用 AWS CLI 测试

```bash
# 设置凭证
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-west-2"

# 测试上传
echo "test" > test.txt
aws s3 cp test.txt s3://2026-demo/test.txt

# 如果成功，应该看到：
# upload: ./test.txt to s3://2026-demo/test.txt

# 测试公共访问（不需要凭证）
aws s3 cp s3://2026-demo/test.txt test-download.txt --no-sign-request

# 清理
aws s3 rm s3://2026-demo/test.txt
rm test.txt test-download.txt
```

### 使用 Python 测试

```python
import boto3

# 测试 1：使用凭证上传
s3 = boto3.client(
    's3',
    aws_access_key_id='your-access-key',
    aws_secret_access_key='your-secret-key',
    region_name='eu-west-2'
)

try:
    s3.put_object(
        Bucket='2026-demo',
        Key='test.txt',
        Body=b'test content'
    )
    print("✅ 使用凭证上传成功")
except Exception as e:
    print(f"❌ 使用凭证上传失败: {e}")

# 测试 2：无凭证上传（如果 bucket policy 允许）
s3_unsigned = boto3.client(
    's3',
    region_name='eu-west-2',
    config=boto3.session.Config(signature_version='UNSIGNED')
)

try:
    s3_unsigned.put_object(
        Bucket='2026-demo',
        Key='test-unsigned.txt',
        Body=b'test content unsigned'
    )
    print("✅ 无凭证上传成功（bucket policy 生效）")
except Exception as e:
    print(f"❌ 无凭证上传失败: {e}")
```

## 推荐配置方案

### 方案 A：完全公共访问（测试环境）

- ✅ Bucket Policy：允许 `Principal: "*"` 读写
- ✅ Block Public Access：禁用
- ⚠️ 不需要 IAM 凭证（但建议保留用于管理）

### 方案 B：IAM 控制访问（生产环境，推荐）

- ✅ Bucket Policy：限制特定 IAM 用户或移除
- ✅ IAM Policy：授予 IAM 用户必要权限
- ✅ Block Public Access：启用（更安全）
- ✅ 使用 IAM 凭证进行所有操作

## 下一步

1. 应用改进后的 bucket policy
2. 检查并禁用 Block Public Access（如果需要）
3. 确保 IAM 用户有正确的 IAM policy
4. 在 Railway 中设置环境变量
5. 重新部署并测试

如果配置正确，应该可以成功上传文件了！
