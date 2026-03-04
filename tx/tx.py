import sys
import os
import json
import re
from pathlib import Path
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class TranslationManager:
    """
    翻译管理器，负责从JSON文件加载英-中双向词典，并提供词汇替换功能。
    词典JSON文件格式应为：
    {
        "words": [
            {"en": "hello", "zh": "你好"},
            {"en": "world", "zh": "世界"}
        ]
    }
    """
    def __init__(self, dict_path=None):
        self.en_to_zh_dict = {}
        self.zh_to_en_dict = {}
        self.dict_path = dict_path
        if dict_path and os.path.exists(dict_path):
            self.load_dictionary(dict_path)

    def load_dictionary(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.en_to_zh_dict.clear()
            self.zh_to_en_dict.clear()
            if "words" in data and isinstance(data["words"], list):
                for item in data["words"]:
                    if isinstance(item, dict) and "en" in item and "zh" in item:
                        en_word = item["en"].strip()
                        zh_word = item["zh"].strip()
                        if en_word and zh_word:
                            self.en_to_zh_dict[en_word.lower()] = {"en": en_word, "zh": zh_word}
                            self.zh_to_en_dict[zh_word] = {"en": en_word, "zh": zh_word}
            print(f"已从 {file_path} 加载翻译词典，包含 {len(self.en_to_zh_dict)} 个词条")
            return True
        except UnicodeDecodeError:
            print(f"加载翻译词典时编码错误: {file_path}，请确保文件为UTF-8编码")
            return False
        except Exception as e:
            print(f"加载翻译词典时出错: {e}")
            return False

    def translate_to_chinese(self, text):
        """将文本中的英文单词（在词典中）替换为中文，返回替换后的文本和替换记录（用于旧版，现仅保留兼容）"""
        if not self.en_to_zh_dict:
            return text, []
        replaced_positions = []
        result_text = ""
        last_end = 0
        pattern = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b')
        for match in pattern.finditer(text):
            word = match.group()
            word_lower = word.lower()
            if word_lower in self.en_to_zh_dict:
                translation = self.en_to_zh_dict[word_lower]["zh"]
                if word[0].isupper():
                    translation = translation[0].upper() + translation[1:] if translation else translation
                result_text += text[last_end:match.start()] + translation
                replaced_positions.append((
                    len(result_text) - len(translation),
                    len(result_text),
                    "zh",
                    word,
                    translation
                ))
                last_end = match.end()
        result_text += text[last_end:]
        return result_text, replaced_positions

    def full_translate_to_english(self, text):
        """
        将文本中的所有中文（在词典中）替换为对应的英文（保留词典中的原始大小写）。
        使用正则匹配连续汉字序列，逐个替换。
        """
        if not self.zh_to_en_dict:
            return text

        # 匹配连续的汉字序列
        zh_pattern = re.compile(r'[\u4e00-\u9fff]+')

        def replace_zh(match):
            zh_word = match.group(0)
            if zh_word in self.zh_to_en_dict:
                return self.zh_to_en_dict[zh_word]["en"]
            return zh_word

        return zh_pattern.sub(replace_zh, text)

class TranslationHighlighter(QSyntaxHighlighter):
    """实时高亮器：基于词典动态扫描当前文本中的可翻译词汇"""
    en_pattern = re.compile(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b')
    zh_pattern = re.compile(r'[\u4e00-\u9fff]+')

    def __init__(self, parent=None, translator=None):
        super().__init__(parent)
        self.translator = translator
        self.zh_format = QTextCharFormat()   # 英->中 颜色
        self.en_format = QTextCharFormat()   # 中->英 颜色
        self.set_zh_color(QColor("#FF0000"))
        self.set_en_color(QColor("#0000FF"))

    def set_translator(self, translator):
        self.translator = translator
        self.rehighlight()

    def set_zh_color(self, color):
        self.zh_format.setForeground(color)
        self.zh_format.setBackground(Qt.transparent)
        self.rehighlight()

    def set_en_color(self, color):
        self.en_format.setForeground(color)
        self.en_format.setBackground(Qt.transparent)
        self.rehighlight()

    def highlightBlock(self, text):
        if not self.translator:
            return
        if not self.translator.en_to_zh_dict and not self.translator.zh_to_en_dict:
            return

        # 高亮英文单词（可翻译为中文）
        if self.translator.en_to_zh_dict:
            for match in self.en_pattern.finditer(text):
                word = match.group()
                if word.lower() in self.translator.en_to_zh_dict:
                    start = match.start()
                    length = match.end() - start
                    self.setFormat(start, length, self.zh_format)

        # 高亮中文词语（可翻译为英文）
        if self.translator.zh_to_en_dict:
            for match in self.zh_pattern.finditer(text):
                word = match.group()
                if word in self.translator.zh_to_en_dict:
                    start = match.start()
                    length = match.end() - start
                    self.setFormat(start, length, self.en_format)

class SearchManager:
    def __init__(self, dict_paths=None):
        self.words = []
        self.words_lower = []          # 预存小写词汇，用于快速搜索
        self.explanations = {}
        if dict_paths:
            for path in dict_paths:
                if os.path.exists(path):
                    self.load_dictionary(path)

    def load_dictionary(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 兼容两种格式：直接是数组，或包含 "words" 键的对象
            if isinstance(data, list):
                items = data
            elif "words" in data and isinstance(data["words"], list):
                items = data["words"]
            else:
                print(f"无法识别的词典格式: {file_path}")
                return False

            for item in items:
                if isinstance(item, dict) and "word" in item:
                    word = item["word"].strip()
                    if word and word not in self.explanations:
                        self.words.append(word)
                        self.words_lower.append(word.lower())
                        self.explanations[word] = item.get("explanation", "")
            print(f"已从 {file_path} 加载 {len([i for i in items if isinstance(i, dict) and 'word' in i])} 个词汇")
            return True
        except UnicodeDecodeError:
            print(f"加载词典文件时编码错误: {file_path}，请确保文件为UTF-8编码")
            return False
        except Exception as e:
            print(f"加载词典文件时出错: {e}")
            return False

    def load_multiple_dictionaries(self, file_paths):
        self.words = []
        self.words_lower = []
        self.explanations.clear()
        for path in file_paths:
            if os.path.exists(path):
                self.load_dictionary(path)
        print(f"总计加载 {len(self.words)} 个词汇（来自 {len(file_paths)} 个文件）")

    def get_explanation(self, word):
        return self.explanations.get(word, "暂无解释")

    def fuzzy_search(self, query, max_results=20):
        if not query or not self.words:
            return []
        query_lower = query.lower()
        q_len = len(query)
        results = []
        # 同时遍历原始词和小写词
        for idx, (word, word_lower) in enumerate(zip(self.words, self.words_lower)):
            pos = word_lower.find(query_lower)
            if pos >= 0:
                # 简单的评分：匹配位置靠前得分高，长度差小得分高
                score = 100 - pos * 2 - abs(len(word) - q_len) * 2
                if word_lower == query_lower:
                    score += 50
                results.append((score, word))
        results.sort(key=lambda x: x[0], reverse=True)
        return [word for _, word in results[:max_results]]

class ConfigManager:
    def __init__(self, config_path=None):
        if config_path is None:
            script_dir = Path(__file__).parent
            self.config_path = script_dir / ".my_rust_assistant_config.json"
        else:
            self.config_path = Path(config_path)
        self.settings = self._load_default_settings()
        self.load()

    def _load_default_settings(self):
        return {
            "window_geometry": None,
            "splitter_sizes": [200, 1000, 200],
            "editor": {
                "font_size": 14,
                "background_image": "",
                "background_opacity": 0.5,
                "theme": "vs_dark"
            },
            "file_tree": {
                "root_path": str(Path.home())
            },
            "auto_save": {
                "enabled": True,
                "interval_seconds": 60
            },
            "completion": {
                "enabled": True,
                "dictionary_paths": [],
                "max_results": 20
            },
            "translation": {
                "enabled": True,
                "dictionary_path": "",
                "highlight_enabled": True,
                "zh_color": "#FF0000",
                "en_color": "#0000FF"
            }
        }

    def load(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self._update_settings(self.settings, loaded_settings)
                print(f"配置已从 {self.config_path} 加载")
            else:
                print("配置文件不存在，使用默认设置")
        except Exception as e:
            print(f"加载配置文件时出错: {e}，使用默认设置")

    def save(self):
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            print(f"配置已保存至 {self.config_path}")
        except Exception as e:
            print(f"保存配置文件时出错: {e}")

    def _update_settings(self, default, new):
        for key, value in new.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._update_settings(default[key], value)
            else:
                default[key] = value

    def get(self, key, default=None):
        keys = key.split('.')
        value = self.settings
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key, value):
        keys = key.split('.')
        target = self.settings
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value

class SettingDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.parent_editor = parent
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 编辑器设置组
        editor_group = QGroupBox("编辑器设置")
        editor_layout = QFormLayout()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(self.config_manager.get("editor.font_size", 14))
        self.font_size_spin.valueChanged.connect(self.apply_font_size)
        editor_layout.addRow("字体大小:", self.font_size_spin)

        bg_layout = QHBoxLayout()
        self.bg_image_line = QLineEdit()
        self.bg_image_line.setText(self.config_manager.get("editor.background_image", ""))
        self.bg_image_line.setReadOnly(True)
        bg_browse_btn = QPushButton("浏览...")
        bg_browse_btn.clicked.connect(self.browse_bg_image)
        bg_clear_btn = QPushButton("清除")
        bg_clear_btn.clicked.connect(self.clear_bg_image)
        bg_layout.addWidget(self.bg_image_line)
        bg_layout.addWidget(bg_browse_btn)
        bg_layout.addWidget(bg_clear_btn)
        editor_layout.addRow("背景图片:", bg_layout)

        self.bg_opacity_slider = QSlider(Qt.Horizontal)
        self.bg_opacity_slider.setRange(0, 100)
        opacity_value = int(self.config_manager.get("editor.background_opacity", 0.5) * 100)
        self.bg_opacity_slider.setValue(opacity_value)
        self.bg_opacity_label = QLabel(f"{opacity_value}%")
        self.bg_opacity_slider.valueChanged.connect(self.on_opacity_changed)
        opacity_layout = QHBoxLayout()
        opacity_layout.addWidget(self.bg_opacity_slider)
        opacity_layout.addWidget(self.bg_opacity_label)
        editor_layout.addRow("背景透明度:", opacity_layout)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["VSCode 暗色主题", "VSCode 浅色主题", "系统默认"])
        current_theme = self.config_manager.get("editor.theme", "vs_dark")
        index_map = {"vs_dark": 0, "vs_light": 1, "system": 2}
        self.theme_combo.setCurrentIndex(index_map.get(current_theme, 0))
        self.theme_combo.currentTextChanged.connect(self.apply_theme)
        editor_layout.addRow("主题:", self.theme_combo)
        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)

        # 文件树设置组
        file_tree_group = QGroupBox("文件树设置")
        file_tree_layout = QFormLayout()
        root_layout = QHBoxLayout()
        self.root_path_line = QLineEdit()
        self.root_path_line.setText(self.config_manager.get("file_tree.root_path", str(Path.home())))
        root_browse_btn = QPushButton("浏览...")
        root_browse_btn.clicked.connect(self.browse_root_path)
        root_layout.addWidget(self.root_path_line)
        root_layout.addWidget(root_browse_btn)
        file_tree_layout.addRow("默认根目录:", root_layout)
        file_tree_group.setLayout(file_tree_layout)
        layout.addWidget(file_tree_group)

        # 自动保存设置组
        auto_save_group = QGroupBox("自动保存设置")
        auto_save_layout = QFormLayout()
        self.auto_save_checkbox = QCheckBox("启用自动保存")
        auto_save_enabled = self.config_manager.get("auto_save.enabled", True)
        self.auto_save_checkbox.setChecked(auto_save_enabled)
        self.auto_save_checkbox.stateChanged.connect(self.on_auto_save_toggled)
        auto_save_layout.addRow(self.auto_save_checkbox)
        self.auto_save_interval_spin = QSpinBox()
        self.auto_save_interval_spin.setRange(10, 3600)
        self.auto_save_interval_spin.setSuffix(" 秒")
        self.auto_save_interval_spin.setValue(self.config_manager.get("auto_save.interval_seconds", 60))
        self.auto_save_interval_spin.setEnabled(auto_save_enabled)
        self.auto_save_interval_spin.valueChanged.connect(self.on_auto_save_interval_changed)
        auto_save_layout.addRow("自动保存间隔:", self.auto_save_interval_spin)
        auto_save_group.setLayout(auto_save_layout)
        layout.addWidget(auto_save_group)

        # 补全提示设置组（支持多个词库文件）
        completion_group = QGroupBox("补全提示设置")
        completion_layout = QFormLayout()
        self.completion_checkbox = QCheckBox("启用补全提示")
        completion_enabled = self.config_manager.get("completion.enabled", True)
        self.completion_checkbox.setChecked(completion_enabled)
        self.completion_checkbox.stateChanged.connect(self.on_completion_toggled)
        completion_layout.addRow(self.completion_checkbox)

        dict_layout = QHBoxLayout()
        self.dict_paths_line = QLineEdit()
        dict_paths = self.config_manager.get("completion.dictionary_paths", [])
        self.dict_paths_line.setText("; ".join(dict_paths))
        self.dict_paths_line.setReadOnly(True)
        dict_browse_btn = QPushButton("浏览...")
        dict_browse_btn.clicked.connect(self.browse_dict_files)
        dict_clear_btn = QPushButton("清除")
        dict_clear_btn.clicked.connect(self.clear_dict_files)
        dict_layout.addWidget(self.dict_paths_line)
        dict_layout.addWidget(dict_browse_btn)
        dict_layout.addWidget(dict_clear_btn)
        completion_layout.addRow("词库文件路径 (JSON，可多选):", dict_layout)

        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(5, 100)
        self.max_results_spin.setValue(self.config_manager.get("completion.max_results", 20))
        self.max_results_spin.valueChanged.connect(self.on_max_results_changed)
        completion_layout.addRow("最大提示结果数:", self.max_results_spin)

        dict_help_label = QLabel("提示：在编辑器输入时，右侧面板会显示匹配词条。使用↑↓选择，按 Tab 键插入。")
        dict_help_label.setStyleSheet("color: #888; font-size: 12px; padding: 5px;")
        dict_help_label.setWordWrap(True)
        completion_layout.addRow("", dict_help_label)
        completion_group.setLayout(completion_layout)
        layout.addWidget(completion_group)

        # 实时翻译编辑设置组
        translation_group = QGroupBox("实时翻译编辑设置")
        translation_layout = QFormLayout()
        self.translation_checkbox = QCheckBox("启用实时翻译编辑模式")
        translation_enabled = self.config_manager.get("translation.enabled", True)
        self.translation_checkbox.setChecked(translation_enabled)
        self.translation_checkbox.stateChanged.connect(self.on_translation_toggled)
        translation_layout.addRow(self.translation_checkbox)

        self.highlight_checkbox = QCheckBox("高亮显示被翻译的词汇")
        highlight_enabled = self.config_manager.get("translation.highlight_enabled", True)
        self.highlight_checkbox.setChecked(highlight_enabled)
        self.highlight_checkbox.stateChanged.connect(self.on_highlight_toggled)
        self.highlight_checkbox.setEnabled(translation_enabled)
        translation_layout.addRow(self.highlight_checkbox)

        trans_dict_layout = QHBoxLayout()
        self.trans_dict_path_line = QLineEdit()
        trans_dict_path = self.config_manager.get("translation.dictionary_path", "")
        self.trans_dict_path_line.setText(trans_dict_path)
        self.trans_dict_path_line.setReadOnly(True)
        trans_dict_browse_btn = QPushButton("浏览...")
        trans_dict_browse_btn.clicked.connect(self.browse_trans_dict_file)
        trans_dict_clear_btn = QPushButton("清除")
        trans_dict_clear_btn.clicked.connect(self.clear_trans_dict_file)
        trans_dict_layout.addWidget(self.trans_dict_path_line)
        trans_dict_layout.addWidget(trans_dict_browse_btn)
        trans_dict_layout.addWidget(trans_dict_clear_btn)
        translation_layout.addRow("翻译词库文件 (JSON):", trans_dict_layout)

        # 字体颜色选择器
        self.zh_color_btn = QPushButton()
        self.zh_color_btn.setFixedSize(50, 25)
        zh_color = self.config_manager.get("translation.zh_color", "#FF0000")
        self.zh_color_btn.setStyleSheet(f"background-color: {zh_color};")
        self.zh_color_btn.clicked.connect(lambda: self.choose_color('zh'))
        self.en_color_btn = QPushButton()
        self.en_color_btn.setFixedSize(50, 25)
        en_color = self.config_manager.get("translation.en_color", "#0000FF")
        self.en_color_btn.setStyleSheet(f"background-color: {en_color};")
        self.en_color_btn.clicked.connect(lambda: self.choose_color('en'))
        translation_layout.addRow("英->中 字体颜色:", self.zh_color_btn)
        translation_layout.addRow("中->英 字体颜色:", self.en_color_btn)

        trans_help_label = QLabel("""提示：启用此功能后，打开文件时其中的英文词汇会自动替换为中文，保存时再转换回英文。编辑过程中可实时高亮显示可翻译词汇。""")
        trans_help_label.setStyleSheet("color: #888; font-size: 12px; padding: 5px;")
        trans_help_label.setWordWrap(True)
        translation_layout.addRow("", trans_help_label)

        translation_group.setLayout(translation_layout)
        layout.addWidget(translation_group)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_and_apply)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    # 以下是所有槽函数定义
    def browse_bg_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.bg_image_line.setText(file_path)
            self.config_manager.set("editor.background_image", file_path)
            self.apply_bg_to_current_editor(file_path)

    def clear_bg_image(self):
        self.bg_image_line.clear()
        self.config_manager.set("editor.background_image", "")
        if self.parent_editor:
            current_editor = self.parent_editor.tab_widget.currentWidget()
            if isinstance(current_editor, CustomTextEdit):
                current_editor.clearBackground()

    def on_opacity_changed(self, value):
        self.bg_opacity_label.setText(f"{value}%")
        opacity = value / 100.0
        self.config_manager.set("editor.background_opacity", opacity)
        if self.parent_editor:
            current_editor = self.parent_editor.tab_widget.currentWidget()
            if isinstance(current_editor, CustomTextEdit):
                current_editor.setBackgroundOpacity(opacity)

    def apply_font_size(self, size):
        self.config_manager.set("editor.font_size", size)
        if self.parent_editor:
            font = self.parent_editor.font()
            font.setPointSize(size)
            for editor in self.parent_editor.editors:
                editor.setFont(font)

    def apply_theme(self, theme_text):
        theme_map = {
            "VSCode 暗色主题": "vs_dark",
            "VSCode 浅色主题": "vs_light",
            "系统默认": "system"
        }
        theme_key = theme_map.get(theme_text, "vs_dark")
        self.config_manager.set("editor.theme", theme_key)
        if self.parent_editor:
            self.parent_editor.apply_style(theme_key)

    def browse_root_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择文件树根目录")
        if dir_path:
            self.root_path_line.setText(dir_path)
            self.config_manager.set("file_tree.root_path", dir_path)
            if self.parent_editor:
                self.parent_editor.file_tree.setRootPath(dir_path)

    def apply_bg_to_current_editor(self, image_path):
        if self.parent_editor:
            current_editor = self.parent_editor.tab_widget.currentWidget()
            if isinstance(current_editor, CustomTextEdit):
                opacity = self.config_manager.get("editor.background_opacity", 0.5)
                current_editor.setBackgroundImage(image_path, opacity)

    def on_auto_save_toggled(self, state):
        enabled = state == Qt.Checked
        self.config_manager.set("auto_save.enabled", enabled)
        self.auto_save_interval_spin.setEnabled(enabled)
        if self.parent_editor:
            if enabled:
                interval = self.config_manager.get("auto_save.interval_seconds", 60)
                self.parent_editor.start_auto_save(interval)
            else:
                self.parent_editor.stop_auto_save()

    def on_auto_save_interval_changed(self, value):
        self.config_manager.set("auto_save.interval_seconds", value)
        if self.parent_editor and self.config_manager.get("auto_save.enabled", False):
            self.parent_editor.start_auto_save(value)

    def browse_dict_files(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择词库文件", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if file_paths:
            self.dict_paths_line.setText("; ".join(file_paths))
            self.config_manager.set("completion.dictionary_paths", file_paths)
            if self.parent_editor and hasattr(self.parent_editor, 'search_manager'):
                self.parent_editor.search_manager.load_multiple_dictionaries(file_paths)
                QMessageBox.information(self, "成功", f"已成功加载 {len(file_paths)} 个词库，总计 {len(self.parent_editor.search_manager.words)} 个词条")
                current_editor = self.parent_editor.tab_widget.currentWidget()
                if current_editor:
                    self.parent_editor.update_search_results(current_editor.toPlainText())

    def clear_dict_files(self):
        self.dict_paths_line.clear()
        self.config_manager.set("completion.dictionary_paths", [])
        if self.parent_editor and hasattr(self.parent_editor, 'search_manager'):
            self.parent_editor.search_manager.words = []
            self.parent_editor.search_manager.words_lower = []
            self.parent_editor.search_manager.explanations.clear()
            self.parent_editor.clear_search_results()

    def on_completion_toggled(self, state):
        enabled = state == Qt.Checked
        self.config_manager.set("completion.enabled", enabled)
        if self.parent_editor:
            if enabled:
                dict_paths = self.config_manager.get("completion.dictionary_paths", [])
                if dict_paths and all(os.path.exists(p) for p in dict_paths):
                    self.parent_editor.search_manager.load_multiple_dictionaries(dict_paths)
                    current_editor = self.parent_editor.tab_widget.currentWidget()
                    if current_editor:
                        self.parent_editor.update_search_results(current_editor.toPlainText())
                else:
                    self.parent_editor.clear_search_results()
                    self.parent_editor.search_status_label.setText("词库文件不存在或未设置")
            else:
                self.parent_editor.clear_search_results()
                self.parent_editor.search_status_label.setText("补全提示已禁用")

    def on_max_results_changed(self, value):
        self.config_manager.set("completion.max_results", value)
        if self.parent_editor:
            current_editor = self.parent_editor.tab_widget.currentWidget()
            if current_editor:
                text = current_editor.toPlainText()
                self.parent_editor.update_search_results(text)

    def on_translation_toggled(self, state):
        enabled = state == Qt.Checked
        self.config_manager.set("translation.enabled", enabled)
        self.highlight_checkbox.setEnabled(enabled)
        if self.parent_editor:
            for editor in self.parent_editor.editors:
                if hasattr(editor, 'original_content'):
                    if enabled:
                        translated, _ = self.parent_editor.translator.translate_to_chinese(editor.original_content)
                        editor.setPlainText(translated)
                    else:
                        editor.setPlainText(editor.original_content)
                    # 更新高亮
                    translator = self.parent_editor.translator if enabled and self.highlight_checkbox.isChecked() else None
                    editor.highlighter.set_translator(translator)

    def on_highlight_toggled(self, state):
        enabled = state == Qt.Checked
        self.config_manager.set("translation.highlight_enabled", enabled)
        if self.parent_editor:
            for editor in self.parent_editor.editors:
                translator = self.parent_editor.translator if enabled and self.config_manager.get("translation.enabled", False) else None
                editor.highlighter.set_translator(translator)

    def browse_trans_dict_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择翻译词库文件", "", "JSON文件 (*.json);;所有文件 (*.*)"
        )
        if file_path:
            self.trans_dict_path_line.setText(file_path)
            self.config_manager.set("translation.dictionary_path", file_path)
            if self.parent_editor and hasattr(self.parent_editor, 'translator'):
                if self.parent_editor.translator.load_dictionary(file_path):
                    QMessageBox.information(self, "成功", f"已成功加载翻译词典，包含 {len(self.parent_editor.translator.en_to_zh_dict)} 个词条")
                    # 刷新所有编辑器的高亮和显示内容
                    if self.config_manager.get("translation.enabled", False):
                        for editor in self.parent_editor.editors:
                            if hasattr(editor, 'original_content'):
                                translated, _ = self.parent_editor.translator.translate_to_chinese(editor.original_content)
                                editor.setPlainText(translated)
                                if self.highlight_checkbox.isChecked():
                                    editor.highlighter.set_translator(self.parent_editor.translator)
                else:
                    QMessageBox.warning(self, "错误", "无法加载翻译词典文件，请检查JSON格式和编码")

    def clear_trans_dict_file(self):
        self.trans_dict_path_line.clear()
        self.config_manager.set("translation.dictionary_path", "")
        if self.parent_editor and hasattr(self.parent_editor, 'translator'):
            self.parent_editor.translator.en_to_zh_dict.clear()
            self.parent_editor.translator.zh_to_en_dict.clear()
            for editor in self.parent_editor.editors:
                editor.highlighter.set_translator(None)
                if self.config_manager.get("translation.enabled", False) and hasattr(editor, 'original_content'):
                    editor.setPlainText(editor.original_content)

    def choose_color(self, target):
        current_color = QColor(self.config_manager.get(f"translation.{target}_color", "#FF0000" if target=='zh' else "#0000FF"))
        color = QColorDialog.getColor(current_color, self, f"选择{ '英->中' if target=='zh' else '中->英' }字体颜色")
        if color.isValid():
            if target == 'zh':
                self.zh_color_btn.setStyleSheet(f"background-color: {color.name()};")
                self.config_manager.set("translation.zh_color", color.name())
            else:
                self.en_color_btn.setStyleSheet(f"background-color: {color.name()};")
                self.config_manager.set("translation.en_color", color.name())
            # 立即应用颜色到所有编辑器
            if self.parent_editor:
                self.parent_editor.update_translation_highlight_colors()

    def accept_and_apply(self):
        self.config_manager.save()
        if self.parent_editor:
            self.parent_editor.update_translation_highlight_colors()
        self.accept()

class CustomTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_image = None
        self.background_pixmap = None
        self.background_opacity = 0.5
        self.file_path = None
        self.parent_window = parent
        self.original_content = ""          # 保存文件的原始英文内容（用于关闭翻译时恢复）
        self.highlighter = TranslationHighlighter(self.document())   # 高亮器初始无 translator

    def setBackgroundImage(self, image_path, opacity=None):
        if os.path.exists(image_path):
            self.background_image = image_path
            self.background_pixmap = QPixmap(image_path)
            if opacity is not None:
                self.background_opacity = max(0.0, min(1.0, opacity))
            self.update()
        else:
            self.clearBackground()

    def setBackgroundOpacity(self, opacity):
        self.background_opacity = max(0.0, min(1.0, opacity))
        self.update()

    def clearBackground(self):
        self.background_image = None
        self.background_pixmap = None
        self.background_opacity = 0.5
        self.update()

    def paintEvent(self, event):
        if self.background_pixmap and not self.background_pixmap.isNull() and self.background_opacity > 0:
            painter = QPainter(self.viewport())
            painter.setOpacity(self.background_opacity)
            pixmap_scaled = self.background_pixmap.scaled(
                self.viewport().size(),
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )
            x = (self.viewport().width() - pixmap_scaled.width()) // 2
            y = (self.viewport().height() - pixmap_scaled.height()) // 2
            painter.drawPixmap(x, y, pixmap_scaled)
            painter.end()
        super().paintEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self.parent_window:
            if hasattr(self.parent_window, 'insert_selected_completion'):
                self.parent_window.insert_selected_completion()
                event.accept()
                return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()
        bg_action = menu.addAction("设置背景图片...")
        opacity_menu = menu.addMenu("设置背景透明度")
        opacity_levels = [
            ("10% (几乎透明)", 0.1),
            ("25%", 0.25),
            ("40%", 0.4),
            ("50% (默认)", 0.5),
            ("60%", 0.6),
            ("75%", 0.75),
            ("90% (几乎不透明)", 0.9)
        ]
        for text, value in opacity_levels:
            action = opacity_menu.addAction(text)
            action.triggered.connect(lambda checked=False, v=value: self.setBackgroundOpacity(v))
        clear_bg_action = menu.addAction("清除背景图片")
        action = menu.exec(event.globalPos())
        if action == bg_action:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if file_path:
                self.setBackgroundImage(file_path)
        elif action == clear_bg_action:
            self.clearBackground()

class FileSystemModel(QFileSystemModel):
    def __init__(self):
        super().__init__()
        self.setRootPath("")

class FileTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = FileSystemModel()
        self.setModel(self.model)
        self.main_window = parent
        for i in range(1, self.model.columnCount()):
            self.hideColumn(i)
        self.doubleClicked.connect(self.on_item_double_clicked)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setAnimated(True) 
        
    def setRootPath(self, path):
        if os.path.exists(path):
            self.model.setRootPath(path)
            self.setRootIndex(self.model.index(path))
        else:
            fallback_path = str(Path.home())
            self.model.setRootPath(fallback_path)
            self.setRootIndex(self.model.index(fallback_path))

    def on_item_double_clicked(self, index):
        file_path = self.model.filePath(index)
        if os.path.isfile(file_path):
            if self.main_window and hasattr(self.main_window, 'load_file'):
                self.main_window.load_file(file_path)
            else:
                parent_window = self.parent()
                while parent_window and not hasattr(parent_window, 'load_file'):
                    parent_window = parent_window.parent()
                if parent_window and hasattr(parent_window, 'load_file'):
                    parent_window.load_file(file_path)
                else:
                    print(f"错误：无法找到可用的 load_file 方法。")

class VSCCodeEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.editors = []
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_all_files)
        self.search_manager = SearchManager()
        self.translator = TranslationManager()
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.perform_search)
        self.last_search_text = ""
        self.current_search_results = []
        self.config_manager = ConfigManager()
        self.initUI()
        self.apply_initial_config()

    def initUI(self):
        self.setWindowTitle("我的铁锈助手Bata")
        self.initUI_from_config()
        self.setAcceptDrops(True)  # 启用拖放

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(200)
        self.left_panel.setMaximumWidth(400)
        left_layout = QVBoxLayout(self.left_panel)
        self.file_tree = FileTreeView(self)
        self.file_tree.setHeaderHidden(True)
        left_toolbar = QToolBar()
        left_toolbar.setIconSize(QSize(16, 16))
        refresh_action = QAction("刷新", self)
        refresh_action.triggered.connect(self.refresh_file_tree)
        new_file_action = QAction("新建文件", self)
        new_file_action.triggered.connect(self.new_file)
        new_folder_action = QAction("新建文件夹", self)
        new_folder_action.triggered.connect(self.new_folder)
        left_toolbar.addAction(refresh_action)
        left_toolbar.addSeparator()
        left_toolbar.addAction(new_file_action)
        left_toolbar.addAction(new_folder_action)
        left_layout.addWidget(left_toolbar)
        left_layout.addWidget(self.file_tree)

        self.middle_panel = QWidget()
        middle_layout = QVBoxLayout(self.middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.create_new_editor("欢迎页", self.get_welcome_content())
        middle_layout.addWidget(self.tab_widget)

        self.right_panel = QWidget()
        self.right_panel.setMinimumWidth(200)
        self.right_panel.setMaximumWidth(400)
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setAlignment(Qt.AlignTop)
        right_title = QLabel("补全提示面板")
        right_title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        right_title.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(right_title)
        self.search_result_list = QListWidget()
        self.search_result_list.setFocusPolicy(Qt.StrongFocus)
        self.search_result_list.currentRowChanged.connect(self.on_search_selection_changed)
        self.search_result_list.itemClicked.connect(self.on_search_item_clicked_for_insert)
        right_layout.addWidget(self.search_result_list, 2)
        explanation_group = QGroupBox("词条解释")
        explanation_layout = QVBoxLayout()
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setMaximumHeight(150)
        explanation_layout.addWidget(self.explanation_text)
        explanation_group.setLayout(explanation_layout)
        right_layout.addWidget(explanation_group, 1)
        self.search_status_label = QLabel("就绪")
        self.search_status_label.setStyleSheet("color: #888; padding: 5px; font-size: 12px;")
        right_layout.addWidget(self.search_status_label)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.middle_panel)
        self.splitter.addWidget(self.right_panel)
        main_layout.addWidget(self.splitter)

        self.create_menu_bar()
        self.statusBar().showMessage("就绪")

    def dragEnterEvent(self, event):
        """拖拽进入时检查是否包含文件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """放下时提取文件路径并打开"""
        urls = event.mimeData().urls()
        for url in urls:
            if url.isLocalFile():
                file_path = url.toLocalFile()
                if os.path.isfile(file_path):
                    self.load_file(file_path)
        event.acceptProposedAction()

    def get_welcome_content(self):
        return """欢迎使用 我的铁锈助手 ！

主要功能：
1. 文件管理：左侧文件树可浏览和打开文件。
2. 代码编辑：支持多标签页编辑，语法高亮。
3. 中文补全提示（支持多个词库）：
   - 在编辑器中输入任意字符，右侧会显示匹配词条。
   - 使用 ↑ ↓ 键选择，按 Tab 键插入选中的词条。
   - 点击右侧列表中的词条可直接插入并查看解释。
4. 实时翻译编辑：
   - 在设置中启用后，打开英文文件时会自动将词典中的词汇替换为中文。
   - 被替换的词汇会实时高亮显示（可自定义字体颜色）。
   - 保存文件时，会自动将中文词汇转换回英文（全文替换）。
5. 个性化设置：通过菜单栏 视图 -> 偏好设置 可自定义编辑器主题、字体、背景、翻译颜色等。

使用提示：
- Ctrl+N: 新建文件
- Ctrl+O: 打开文件
- Ctrl+S: 保存文件
- Ctrl+Shift+S: 全部保存
- Ctrl+Q: 退出程序
- Ctrl+,: 打开设置
- 您也可以直接将文件拖入窗口打开。

开始使用：
1. 在设置中指定您的词库文件（可多选）。
2. 在设置中启用并配置实时翻译编辑功能。
3. 在左侧文件树中浏览您的项目。
4. 在编辑器中输入以体验补全提示功能。
"""

    def initUI_from_config(self):
        saved_geometry = self.config_manager.get("window_geometry")
        if saved_geometry:
            self.restoreGeometry(QByteArray.fromBase64(saved_geometry.encode()))
        else:
            self.setGeometry(100, 100, 1400, 800)

    def create_new_editor(self, title, content="", file_path=None):
        editor = CustomTextEdit()
        editor.setPlainText(content)
        editor.textChanged.connect(self.on_text_changed_with_search)
        editor.parent_window = self
        if file_path:
            editor.file_path = file_path

        if file_path:
            index = self.tab_widget.addTab(editor, os.path.basename(file_path))
        else:
            index = self.tab_widget.addTab(editor, title)

        self.tab_widget.setCurrentIndex(index)
        self.editors.append(editor)
        self.apply_background_to_editor(editor)

        # 设置高亮器的 translator（根据配置）
        translation_enabled = self.config_manager.get("translation.enabled", False)
        highlight_enabled = self.config_manager.get("translation.highlight_enabled", True)
        if translation_enabled and highlight_enabled:
            editor.highlighter.set_translator(self.translator)
        else:
            editor.highlighter.set_translator(None)

        return editor

    def apply_background_to_editor(self, editor):
        bg_image = self.config_manager.get("editor.background_image")
        bg_opacity = self.config_manager.get("editor.background_opacity", 0.5)
        if bg_image and os.path.exists(bg_image) and isinstance(editor, CustomTextEdit):
            editor.setBackgroundImage(bg_image, bg_opacity)

    def close_tab(self, index):
        """关闭标签页，带淡出动画"""
        widget = self.tab_widget.widget(index)
        if not widget:
            return

        # 如果是欢迎页且不是最后一个标签，按原有方式关闭（不添加动画，以免影响其他）
        if self.tab_widget.count() == 1:
            # 最后一个标签页，直接清空并重置为欢迎页
            widget.clear()
            widget.setPlainText(self.get_welcome_content())
            self.tab_widget.setTabText(0, "欢迎页")
            self.editors[0].file_path = None
            self.clear_search_results()
            return

        # 创建透明度效果
        opacity_effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(opacity_effect)
        # 创建动画（每个标签独立动画对象，保存在字典中避免覆盖）
        if not hasattr(self, '_fade_animations'):
            self._fade_animations = {}
        animation = QPropertyAnimation(opacity_effect, b"opacity")
        animation.setDuration(200)  # 200ms
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(lambda: self._remove_tab_after_fade(index, widget, animation))
        self._fade_animations[index] = animation
        animation.start()

    def _remove_tab_after_fade(self, index, widget, animation):
        """淡出结束后实际移除标签页"""
        self.tab_widget.removeTab(index)
        if widget in self.editors:
            self.editors.remove(widget)
        # 清理图形效果和动画引用
        widget.setGraphicsEffect(None)
        if hasattr(self, '_fade_animations') and index in self._fade_animations:
            del self._fade_animations[index]

    def on_tab_changed(self, index):
        if index >= 0 and index < len(self.editors):
            editor = self.editors[index]
            self.update_search_results(editor.toPlainText())
            # 状态栏显示翻译信息
            if self.config_manager.get("translation.enabled", False) and editor.original_content:
                self.statusBar().showMessage("翻译模式已启用")
            else:
                self.statusBar().showMessage("就绪")

    def on_search_selection_changed(self, row):
        if row < 0 or row >= self.search_result_list.count():
            self.explanation_text.clear()
            return
        item = self.search_result_list.item(row)
        if not item:
            return
        self._display_explanation_for_item(item)

    def on_search_item_clicked_for_insert(self, item):
        if not item:
            return
        self._display_explanation_for_item(item)
        self._insert_completion_from_item(item)

    def _display_explanation_for_item(self, item):
        display_text = item.text()
        import re
        match = re.match(r'^\s*\d+\.\s*(.+)', display_text)
        if match:
            word = match.group(1)
        else:
            word = display_text
        explanation = self.search_manager.get_explanation(word)
        if explanation:
            explanation_html = explanation.replace('\n', '<br>')
            self.explanation_text.setHtml(f"""
            <div style='color: #d4d4d4; font-size: 13px; padding: 5px;'>
                <h3 style='color: #569cd6; margin-top: 0;'>{word}</h3>
                <hr style='border: 1px solid #3c3c3c;'>
                <p>{explanation_html}</p>
            </div>
            """)
        else:
            self.explanation_text.setText(f"【{word}】\n暂无解释")

    def _insert_completion_from_item(self, item):
        display_text = item.text()
        import re
        match = re.match(r'^\s*\d+\.\s*(.+)', display_text)
        if match:
            word_to_insert = match.group(1)
        else:
            word_to_insert = display_text

        current_editor = self.tab_widget.currentWidget()
        if not current_editor:
            return

        cursor = current_editor.textCursor()
        editor_text = current_editor.toPlainText()
        cursor_pos = cursor.position()

        text_before = editor_text[:cursor_pos]
        import re
        match_before = re.search(r'([\u4e00-\u9fff\w]+)$', text_before)
        if match_before:
            last_word = match_before.group(1)
            if word_to_insert.startswith(last_word):
                chars_to_delete = len(last_word)
                cursor.movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, chars_to_delete)
                cursor.removeSelectedText()

        cursor.insertText(word_to_insert)
        current_editor.setTextCursor(cursor)

        # 动画：高亮被点击的项（橙色闪烁）
        original_bg = item.background()
        item.setBackground(QColor("#FFA500"))  # 橙色
        QTimer.singleShot(200, lambda: item.setBackground(original_bg))

        self.clear_search_results()
        self.search_status_label.setText(f"已插入: {word_to_insert}")

    def insert_selected_completion(self):
        if not self.current_search_results:
            current_editor = self.tab_widget.currentWidget()
            if current_editor:
                cursor = current_editor.textCursor()
                cursor.insertText("\t")
            return

        current_row = self.search_result_list.currentRow()
        if current_row >= 0 and current_row < self.search_result_list.count():
            item = self.search_result_list.item(current_row)
            self._insert_completion_from_item(item)
        else:
            if self.search_result_list.count() > 0:
                self.search_result_list.setCurrentRow(0)
                item = self.search_result_list.item(0)
                self._insert_completion_from_item(item)
            else:
                current_editor = self.tab_widget.currentWidget()
                if current_editor:
                    cursor = current_editor.textCursor()
                    cursor.insertText("\t")

    def clear_search_results(self):
        self.search_result_list.clear()
        self.explanation_text.clear()
        self.current_search_results = []
        self.last_search_text = ""

    def create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("文件")
        new_action = QAction("新建", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_file)
        open_action = QAction("打开", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        save_action = QAction("保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)
        save_as_action = QAction("另存为", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)
        save_all_action = QAction("全部保存", self)
        save_all_action.setShortcut("Ctrl+Alt+S")
        save_all_action.triggered.connect(self.save_all_files)
        exit_action = QAction("退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(new_action)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addAction(save_all_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("编辑")
        undo_action = QAction("撤销", self)
        undo_action.setShortcut("Ctrl+Z")
        undo_action.triggered.connect(lambda: self.tab_widget.currentWidget().undo() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(undo_action)
        redo_action = QAction("重做", self)
        redo_action.setShortcut("Ctrl+Y")
        redo_action.triggered.connect(lambda: self.tab_widget.currentWidget().redo() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(redo_action)
        edit_menu.addSeparator()
        cut_action = QAction("剪切", self)
        cut_action.setShortcut("Ctrl+X")
        cut_action.triggered.connect(lambda: self.tab_widget.currentWidget().cut() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(cut_action)
        copy_action = QAction("复制", self)
        copy_action.setShortcut("Ctrl+C")
        copy_action.triggered.connect(lambda: self.tab_widget.currentWidget().copy() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(copy_action)
        paste_action = QAction("粘贴", self)
        paste_action.setShortcut("Ctrl+V")
        paste_action.triggered.connect(lambda: self.tab_widget.currentWidget().paste() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(paste_action)
        edit_menu.addSeparator()
        select_all_action = QAction("全选", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(lambda: self.tab_widget.currentWidget().selectAll() if self.tab_widget.currentWidget() else None)
        edit_menu.addAction(select_all_action)

        view_menu = menubar.addMenu("视图")
        toggle_left_action = QAction("切换左侧面板", self)
        toggle_left_action.triggered.connect(lambda: self.toggle_panel(self.left_panel))
        toggle_right_action = QAction("切换右侧面板", self)
        toggle_right_action.triggered.connect(lambda: self.toggle_panel(self.right_panel))
        bg_action = QAction("设置编辑器背景...", self)
        bg_action.triggered.connect(self.set_editor_background)
        settings_action = QAction("偏好设置...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings_dialog)
        view_menu.addAction(toggle_left_action)
        view_menu.addAction(toggle_right_action)
        view_menu.addSeparator()
        view_menu.addAction(bg_action)
        view_menu.addSeparator()
        view_menu.addAction(settings_action)

    def apply_initial_config(self):
        theme = self.config_manager.get("editor.theme", "vs_dark")
        self.apply_style(theme)
        font_size = self.config_manager.get("editor.font_size", 14)
        font = self.font()
        font.setPointSize(font_size)
        self.setFont(font)
        for editor in self.editors:
            editor.setFont(font)
        root_path = self.config_manager.get("file_tree.root_path", str(Path.home()))
        self.file_tree.setRootPath(root_path)
        splitter_sizes = self.config_manager.get("splitter_sizes", [200, 1000, 200])
        if self.splitter:
            self.splitter.setSizes(splitter_sizes)
        bg_image = self.config_manager.get("editor.background_image")
        bg_opacity = self.config_manager.get("editor.background_opacity", 0.5)
        if bg_image and os.path.exists(bg_image):
            for editor in self.editors:
                if isinstance(editor, CustomTextEdit):
                    editor.setBackgroundImage(bg_image, bg_opacity)

        auto_save_enabled = self.config_manager.get("auto_save.enabled", True)
        auto_save_interval = self.config_manager.get("auto_save.interval_seconds", 60)
        if auto_save_enabled:
            self.start_auto_save(auto_save_interval)
        else:
            self.stop_auto_save()

        completion_enabled = self.config_manager.get("completion.enabled", True)
        dict_paths = self.config_manager.get("completion.dictionary_paths", [])
        if completion_enabled and dict_paths and all(os.path.exists(p) for p in dict_paths):
            self.search_manager.load_multiple_dictionaries(dict_paths)
            self.search_status_label.setText(f"就绪 | 词库: {len(self.search_manager.words)} 词条 (来自 {len(dict_paths)} 个文件)")
        elif completion_enabled and dict_paths and not all(os.path.exists(p) for p in dict_paths):
            self.search_status_label.setText("部分词库文件不存在")
            self.search_manager.words = []
            self.search_manager.words_lower = []
            self.search_manager.explanations.clear()
        elif completion_enabled and not dict_paths:
            self.search_status_label.setText("未设置词库文件")
        else:
            self.search_status_label.setText("补全提示已禁用")
            self.clear_search_results()

        translation_enabled = self.config_manager.get("translation.enabled", True)
        trans_dict_path = self.config_manager.get("translation.dictionary_path", "")
        if translation_enabled and trans_dict_path and os.path.exists(trans_dict_path):
            if self.translator.load_dictionary(trans_dict_path):
                self.statusBar().showMessage(f"翻译模式就绪 | 词典: {len(self.translator.en_to_zh_dict)} 词条")
            else:
                self.statusBar().showMessage("翻译词典加载失败")
        elif translation_enabled and trans_dict_path and not os.path.exists(trans_dict_path):
            self.statusBar().showMessage("翻译词典文件不存在")
        elif not translation_enabled:
            self.statusBar().showMessage("就绪")

        self.update_translation_highlight_colors()

    def update_translation_highlight_colors(self):
        zh_color = QColor(self.config_manager.get("translation.zh_color", "#FF0000"))
        en_color = QColor(self.config_manager.get("translation.en_color", "#0000FF"))
        for editor in self.editors:
            if hasattr(editor, 'highlighter'):
                editor.highlighter.set_zh_color(zh_color)
                editor.highlighter.set_en_color(en_color)
                # 重新关联 translator（可能已变化）
                if self.config_manager.get("translation.enabled", False) and self.config_manager.get("translation.highlight_enabled", True):
                    editor.highlighter.set_translator(self.translator)
                else:
                    editor.highlighter.set_translator(None)

    def apply_style(self, theme="vs_dark"):
        if theme == "vs_dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1e1e1e;
                }
                QWidget {
                    color: #cccccc;
                    background-color: #252526;
                    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                }
                QTabWidget::pane {
                    border: 1px solid #3c3c3c;
                    background-color: #1e1e1e;
                }
                QTabBar::tab {
                    background-color: #2d2d30;
                    color: #cccccc;
                    padding: 8px 12px;
                    margin-right: 2px;
                    border: 1px solid #3c3c3c;
                    border-bottom: none;
                }
                QTabBar::tab:selected {
                    background-color: #1e1e1e;
                    border-bottom: 2px solid #007acc;
                }
                QTabBar::tab:hover:!selected {
                    background-color: #2a2d2e;
                }
                QTextEdit, QPlainTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: none;
                    selection-background-color: #264f78;
                }
                QListWidget {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    outline: none;
                }
                QListWidget::item {
                    padding: 6px;
                    border-bottom: 1px solid #2d2d30;
                }
                QListWidget::item:selected {
                    background-color: #094771;
                    color: white;
                }
                QListWidget::item:hover {
                    background-color: #2a2d2e;
                }
                QTreeView {
                    background-color: #252526;
                    alternate-background-color: #2d2d30;
                    border: none;
                    outline: 0;
                }
                QTreeView::item {
                    padding: 2px;
                    border: 1px solid transparent;
                }
                QTreeView::item:selected {
                    background-color: #094771;
                    color: white;
                }
                QTreeView::item:hover {
                    background-color: #2a2d2e;
                }
                QGroupBox {
                    border: 1px solid #3c3c3c;
                    border-radius: 4px;
                    margin-top: 10px;
                    padding-top: 10px;
                    font-weight: bold;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px 0 5px;
                }
                QSplitter::handle {
                    background-color: #3c3c3c;
                    width: 1px;
                }
                QSplitter::handle:hover {
                    background-color: #007acc;
                }
                QToolBar {
                    background-color: #333333;
                    border: none;
                    spacing: 2px;
                }
                QToolBar QToolButton {
                    background-color: transparent;
                    border: 1px solid transparent;
                    padding: 4px;
                    border-radius: 4px;
                }
                QToolBar QToolButton:hover {
                    background-color: #2a2d2e;
                    border: 1px solid #3c3c3c;
                }
                QPushButton {
                    background-color: #0e639c;
                    color: white;
                    border: none;
                    padding: 8px;
                    border-radius: 4px;
                    margin: 2px;
                }
                QPushButton:hover {
                    background-color: #1177bb;
                }
                QMenuBar {
                    background-color: #3c3c3c;
                }
                QMenuBar::item:selected {
                    background-color: #2a2d2e;
                }
                QMenu {
                    background-color: #252526;
                    border: 1px solid #3c3c3c;
                }
                QMenu::item:selected {
                    background-color: #094771;
                }
                QScrollBar:vertical {
                    background-color: #1e1e1e;
                    width: 12px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background-color: #424242;
                    min-height: 20px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background-color: #5a5a5a;
                }
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                    height: 0px;
                }
            """)
        elif theme == "vs_light":
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #f3f3f3;
                    color: #333333;
                }
                QTextEdit, QPlainTextEdit {
                    background-color: white;
                    color: black;
                }
            """)
        else:
            self.setStyleSheet("")

    def start_auto_save(self, interval_seconds):
        if self.auto_save_timer.isActive():
            self.auto_save_timer.stop()
        self.auto_save_timer.start(interval_seconds * 1000)
        self.statusBar().showMessage(f"自动保存已启用，间隔 {interval_seconds} 秒")

    def stop_auto_save(self):
        if self.auto_save_timer.isActive():
            self.auto_save_timer.stop()
        self.statusBar().showMessage("自动保存已禁用")

    def auto_save_all_files(self):
        saved_count = 0
        errors = []
        for editor in self.editors:
            if hasattr(editor, 'file_path') and editor.file_path and os.path.exists(os.path.dirname(editor.file_path)):
                try:
                    content = editor.toPlainText()
                    if self.config_manager.get("translation.enabled", False):
                        # 使用全文替换将中文转回英文
                        content_to_save = self.translator.full_translate_to_english(content)
                    else:
                        content_to_save = content

                    with open(editor.file_path, 'w', encoding='utf-8') as f:
                        f.write(content_to_save)
                    saved_count += 1
                    for i in range(self.tab_widget.count()):
                        if self.tab_widget.widget(i) == editor:
                            tab_text = self.tab_widget.tabText(i)
                            if tab_text.startswith("* "):
                                self.tab_widget.setTabText(i, tab_text[2:])
                            break
                except Exception as e:
                    errors.append(f"{editor.file_path}: {str(e)}")
        if saved_count > 0:
            msg = f"已自动保存 {saved_count} 个文件"
            if errors:
                msg += f"，{len(errors)} 个文件保存失败"
            self.statusBar().showMessage(msg)
        if errors:
            # 可以弹出提示，但自动保存时不频繁打扰，仅打印到控制台
            print("自动保存失败:", errors)

    def save_all_files(self):
        self.auto_save_all_files()

    def on_text_changed_with_search(self):
        current_index = self.tab_widget.currentIndex()
        tab_text = self.tab_widget.tabText(current_index)
        if not tab_text.startswith("* "):
            self.tab_widget.setTabText(current_index, f"* {tab_text}")
        self.search_timer.stop()
        self.search_timer.start(300)

    def perform_search(self):
        if not self.config_manager.get("completion.enabled", True):
            return
        current_editor = self.tab_widget.currentWidget()
        if current_editor:
            text = current_editor.toPlainText()
            if text == self.last_search_text:
                return
            self.last_search_text = text
            self.update_search_results(text)

    def get_current_word_at_cursor(self, editor):
        cursor = editor.textCursor()
        pos = cursor.position()
        text = editor.toPlainText()[:pos]
        match = re.search(r'([\u4e00-\u9fff\w]+)$', text)
        if match:
            return match.group(1)
        return ""

    def update_search_results(self, text):
        if not self.config_manager.get("completion.enabled", True):
            self.search_result_list.clear()
            self.search_result_list.addItem("补全提示功能已禁用")
            self.search_status_label.setText("补全提示已禁用")
            return

        dict_paths = self.config_manager.get("completion.dictionary_paths", [])
        if not dict_paths:
            self.search_result_list.clear()
            self.search_result_list.addItem("未设置词库文件")
            self.explanation_text.clear()
            self.search_status_label.setText("词库文件未设置")
            return

        if not all(os.path.exists(p) for p in dict_paths):
            self.search_result_list.clear()
            self.search_result_list.addItem("部分词库文件不存在，请检查设置")
            self.explanation_text.clear()
            self.search_status_label.setText("词库文件缺失")
            return

        if not self.search_manager.words and dict_paths:
            self.search_manager.load_multiple_dictionaries(dict_paths)

        current_editor = self.tab_widget.currentWidget()
        if not current_editor:
            return

        query = self.get_current_word_at_cursor(current_editor)
        if len(query) < 2:   # 优化：至少输入2个字符才触发搜索
            self.search_result_list.clear()
            self.search_result_list.addItem("请输入至少2个字符以触发搜索")
            self.explanation_text.clear()
            self.search_status_label.setText(f"就绪 | 词库: {len(self.search_manager.words)} 词条")
            return

        max_results = self.config_manager.get("completion.max_results", 20)
        results = self.search_manager.fuzzy_search(query, max_results)
        self.current_search_results = results
        self.search_result_list.clear()
        self.explanation_text.clear()

        if results:
            for i, word in enumerate(results, 1):
                self.search_result_list.addItem(f"{i:2d}. {word}")
            if self.search_result_list.count() > 0:
                self.search_result_list.setCurrentRow(0)
                first_item = self.search_result_list.item(0)
                self._display_explanation_for_item(first_item)
            self.search_status_label.setText(f"找到 {len(results)} 个提示 | 输入: '{query}' | 词库: {len(self.search_manager.words)} 词条")
        else:
            self.search_result_list.addItem(f"输入: '{query}'")
            self.search_result_list.addItem("")
            self.search_result_list.addItem("未找到匹配词条。")
            self.search_status_label.setText(f"无匹配 | 输入: '{query}' | 词库: {len(self.search_manager.words)} 词条")

    def new_file(self):
        self.create_new_editor("无标题")
        self.statusBar().showMessage("已创建新文件")

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "All Files (*.*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # 确定显示内容（如果翻译启用，则转换为中文）
            translation_enabled = self.config_manager.get("translation.enabled", True)
            if translation_enabled and self.translator.en_to_zh_dict:
                display_content, _ = self.translator.translate_to_chinese(original_content)
                self.statusBar().showMessage(f"已加载文件并翻译 {len(self.translator.en_to_zh_dict)} 处词汇")
            else:
                display_content = original_content
                self.statusBar().showMessage(f"已打开: {file_path}")

            # 检查是否已打开此文件
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if hasattr(widget, 'file_path') and widget.file_path == file_path:
                    self.tab_widget.setCurrentIndex(i)
                    widget.setPlainText(display_content)
                    widget.original_content = original_content
                    # 更新高亮器
                    if translation_enabled and self.config_manager.get("translation.highlight_enabled", True):
                        widget.highlighter.set_translator(self.translator)
                    else:
                        widget.highlighter.set_translator(None)
                    self.update_search_results(display_content)
                    return

            # 创建新标签
            editor = self.create_new_editor(os.path.basename(file_path), display_content, file_path)
            editor.file_path = file_path
            editor.original_content = original_content
            # 高亮器已在 create_new_editor 中根据配置设置，但此处确保 translator 存在
            if translation_enabled and self.config_manager.get("translation.highlight_enabled", True):
                editor.highlighter.set_translator(self.translator)
            else:
                editor.highlighter.set_translator(None)

            self.current_file = file_path
            self.apply_background_to_editor(editor)
            self.update_search_results(display_content)

        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法打开文件: {str(e)}")

    def save_file(self):
        current_widget = self.tab_widget.currentWidget()
        if hasattr(current_widget, 'file_path') and current_widget.file_path:
            self._save_to_file(current_widget.file_path, current_widget.toPlainText())
        else:
            self.save_file_as()

    def save_file_as(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存文件", "", "All Files (*.*)"
        )
        if file_path:
            current_widget = self.tab_widget.currentWidget()
            if self._save_to_file(file_path, current_widget.toPlainText()):
                current_widget.file_path = file_path
                self.tab_widget.setTabText(self.tab_widget.currentIndex(), os.path.basename(file_path))

    def _save_to_file(self, file_path, content):
        try:
            if self.config_manager.get("translation.enabled", True):
                # 全文替换为英文
                content_to_save = self.translator.full_translate_to_english(content)
            else:
                content_to_save = content

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content_to_save)
            self.statusBar().showMessage(f"已保存: {file_path}")

            # 保存动画：状态栏闪烁绿色
            original_style = self.statusBar().styleSheet()
            self.statusBar().setStyleSheet("QStatusBar { background-color: #00FF00; color: black; }")
            QTimer.singleShot(300, lambda: self.statusBar().setStyleSheet(original_style))

            current_index = self.tab_widget.currentIndex()
            tab_text = self.tab_widget.tabText(current_index)
            if tab_text.startswith("* "):
                self.tab_widget.setTabText(current_index, tab_text[2:])

            return True
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法保存文件: {str(e)}")
            return False

    def new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "新建文件夹", "输入文件夹名称:")
        if ok and folder_name:
            current_dir = self.file_tree.model.rootPath()
            if not current_dir:
                current_dir = str(Path.home())
            new_folder_path = os.path.join(current_dir, folder_name)
            try:
                os.makedirs(new_folder_path, exist_ok=True)
                self.refresh_file_tree()
                self.statusBar().showMessage(f"已创建文件夹: {folder_name}")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法创建文件夹: {str(e)}")

    def refresh_file_tree(self):
        root_path = self.file_tree.model.rootPath()
        if not root_path:
            root_path = str(Path.home())
        self.file_tree.model.setRootPath("")
        self.file_tree.model.setRootPath(root_path)
        self.file_tree.setRootIndex(self.file_tree.model.index(root_path))

    def set_editor_background(self):
        current_editor = self.tab_widget.currentWidget()
        if isinstance(current_editor, CustomTextEdit):
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择背景图片", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if file_path:
                current_editor.setBackgroundImage(file_path)
                self.config_manager.set("editor.background_image", file_path)

    def toggle_panel(self, panel):
        panel.setVisible(not panel.isVisible())

    def show_settings_dialog(self):
        dialog = SettingDialog(self.config_manager, self)
        if dialog.exec():
            self.statusBar().showMessage("设置已保存并应用")
        else:
            self.statusBar().showMessage("设置已取消")

    def closeEvent(self, event):
        if self.config_manager.get("auto_save.enabled", False):
            self.auto_save_all_files()
            self.statusBar().showMessage("程序关闭，已自动保存文件")
        geometry = self.saveGeometry().toBase64().data().decode()
        self.config_manager.set("window_geometry", geometry)
        if self.splitter:
            self.config_manager.set("splitter_sizes", self.splitter.sizes())
        self.config_manager.save()
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    editor = VSCCodeEditor()
    editor.show()
    editor.activateWindow()
    editor.raise_()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()