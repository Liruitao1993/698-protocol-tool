import sqlite3
import os
from typing import List, Dict, Optional, Tuple
from PySide6.QtCore import QObject, Signal

class DatabaseHandler(QObject):
    """数据库操作类，处理帧数据的CRUD操作"""
    
    # 定义数据库信号
    data_changed = Signal()  # 数据变更信号
    
    def __init__(self, db_path: str = "frames.db"):
        super().__init__()
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """初始化数据库，创建表结构"""
        try:
            # 确保数据库目录存在
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建frames表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS frames (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    frame_content TEXT NOT NULL,
                    operation TEXT DEFAULT '单帧发送',
                    status TEXT DEFAULT '未发送',
                    match_enabled INTEGER DEFAULT 0,
                    match_rule TEXT DEFAULT '',
                    match_mode TEXT DEFAULT 'HEX',
                    test_result TEXT DEFAULT '',
                    timeout_ms INTEGER DEFAULT 1000,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建触发器，在更新时自动更新updated_at字段
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS update_frames_timestamp 
                AFTER UPDATE ON frames
                FOR EACH ROW
                BEGIN
                    UPDATE frames SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
                END
            ''')
            
            conn.commit()
            conn.close()
            print(f"数据库初始化成功: {self.db_path}")
            
        except Exception as e:
            print(f"数据库初始化失败: {e}")
            raise
    
    def add_frame(self, name: str, frame_content: str, **kwargs) -> int:
        """添加新帧，返回记录ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 设置默认值
            defaults = {
                'operation': '单帧发送',
                'status': '未发送', 
                'match_enabled': 0,
                'match_rule': '',
                'match_mode': 'HEX',
                'test_result': '',
                'timeout_ms': 1000
            }
            defaults.update(kwargs)
            
            cursor.execute('''
                INSERT INTO frames (name, frame_content, operation, status, match_enabled, 
                                  match_rule, match_mode, test_result, timeout_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, frame_content, defaults['operation'], defaults['status'],
                  defaults['match_enabled'], defaults['match_rule'], defaults['match_mode'],
                  defaults['test_result'], defaults['timeout_ms']))
            
            frame_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            # 发射数据变更信号
            self.data_changed.emit()
            
            return frame_id
            
        except Exception as e:
            print(f"添加帧失败: {e}")
            raise
    
    def get_all_frames(self) -> List[Dict]:
        """获取所有帧数据，按ID升序排列"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, frame_content, operation, status, match_enabled,
                       match_rule, match_mode, test_result, timeout_ms, created_at, updated_at
                FROM frames
                ORDER BY id ASC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # 转换为字典列表
            frames = []
            for row in rows:
                frames.append({
                    'id': row[0],
                    'name': row[1],
                    'frame_content': row[2],
                    'operation': row[3],
                    'status': row[4],
                    'match_enabled': bool(row[5]),
                    'match_rule': row[6] or '',
                    'match_mode': row[7] or 'HEX',
                    'test_result': row[8] or '',
                    'timeout_ms': row[9] or 1000,
                    'created_at': row[10],
                    'updated_at': row[11]
                })
            
            return frames
            
        except Exception as e:
            print(f"获取帧数据失败: {e}")
            return []
    
    def update_frame(self, frame_id: int, emit_signal: bool = True, **kwargs) -> bool:
        """更新帧数据
        
        Args:
            frame_id: 帧ID
            emit_signal: 是否发射数据变更信号，默认True
            **kwargs: 要更新的字段
        """
        try:
            if not kwargs:
                return True
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 构建更新语句
            update_fields = []
            values = []
            
            allowed_fields = ['name', 'frame_content', 'operation', 'status', 'match_enabled',
                            'match_rule', 'match_mode', 'test_result', 'timeout_ms']
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    if field == 'match_enabled':
                        update_fields.append(f"{field} = ?")
                        values.append(1 if value else 0)
                    else:
                        update_fields.append(f"{field} = ?")
                        values.append(value)
            
            if not update_fields:
                return True
            
            values.append(frame_id)
            sql = f"UPDATE frames SET {', '.join(update_fields)} WHERE id = ?"
            
            cursor.execute(sql, values)
            conn.commit()
            conn.close()
            
            # 根据参数决定是否发射数据变更信号
            if emit_signal:
                self.data_changed.emit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"更新帧失败: {e}")
            return False
    
    def delete_frame(self, frame_id: int) -> bool:
        """删除帧"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM frames WHERE id = ?", (frame_id,))
            
            conn.commit()
            conn.close()
            
            # 发射数据变更信号
            self.data_changed.emit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            print(f"删除帧失败: {e}")
            return False
    
    def delete_frames(self, frame_ids: List[int]) -> int:
        """批量删除帧，返回删除的记录数"""
        try:
            if not frame_ids:
                return 0
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            placeholders = ','.join(['?' for _ in frame_ids])
            cursor.execute(f"DELETE FROM frames WHERE id IN ({placeholders})", frame_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            # 发射数据变更信号
            self.data_changed.emit()
            
            return deleted_count
            
        except Exception as e:
            print(f"批量删除帧失败: {e}")
            return 0
    
    def get_frame(self, frame_id: int) -> Optional[Dict]:
        """获取指定ID的帧数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, frame_content, operation, status, match_enabled,
                       match_rule, match_mode, test_result, timeout_ms, created_at, updated_at
                FROM frames WHERE id = ?
            ''', (frame_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'name': row[1],
                    'frame_content': row[2],
                    'operation': row[3],
                    'status': row[4],
                    'match_enabled': bool(row[5]),
                    'match_rule': row[6] or '',
                    'match_mode': row[7] or 'HEX',
                    'test_result': row[8] or '',
                    'timeout_ms': row[9] or 1000,
                    'created_at': row[10],
                    'updated_at': row[11]
                }
            return None
            
        except Exception as e:
            print(f"获取帧数据失败: {e}")
            return None
    
    def clear_all_frames(self) -> bool:
        """清空所有帧数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM frames")
            
            conn.commit()
            conn.close()
            
            # 发射数据变更信号
            self.data_changed.emit()
            
            return True
            
        except Exception as e:
            print(f"清空帧数据失败: {e}")
            return False
    
    def export_to_dict(self) -> List[Dict]:
        """导出所有帧数据为字典列表（用于CSV导出）"""
        frames = self.get_all_frames()
        export_data = []
        
        for frame in frames:
            export_data.append({
                'name': frame['name'],
                'frame_content': frame['frame_content'],
                'status': frame['status'],
                'match_enabled': '1' if frame['match_enabled'] else '0',
                'match_rule': frame['match_rule'],
                'match_mode': frame['match_mode'],
                'test_result': frame['test_result'],
                'timeout_ms': frame['timeout_ms']
            })
        
        return export_data
    
    def import_from_dict(self, frames_data: List[Dict]) -> int:
        """从字典列表导入帧数据，返回导入的记录数"""
        imported_count = 0
        try:
            for frame_data in frames_data:
                self.add_frame(
                    name=frame_data.get('name', ''),
                    frame_content=frame_data.get('frame_content', ''),
                    status=frame_data.get('status', '未发送'),
                    match_enabled=frame_data.get('match_enabled', '0') == '1',
                    match_rule=frame_data.get('match_rule', ''),
                    match_mode=frame_data.get('match_mode', 'HEX'),
                    test_result=frame_data.get('test_result', ''),
                    timeout_ms=frame_data.get('timeout_ms', 1000)
                )
                imported_count += 1
        except Exception as e:
            print(f"导入帧数据失败: {e}")
            
        return imported_count