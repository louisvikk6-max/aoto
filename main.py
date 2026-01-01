#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class BossAutoDeliver:
    def __init__(self):
        self.config = self.load_config()
        self.delivered_jobs = self.load_delivered_jobs()
        self.driver = None
        self.today_count = 0

    def load_config(self):
        """加载配置文件"""
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("配置文件config.json不存在！")
            exit(1)

    def load_delivered_jobs(self):
        """加载已投递记录"""
        try:
            with open('delivered.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 只保留今天的记录
                today = datetime.now().strftime('%Y-%m-%d')
                if data.get('date') == today:
                    return data.get('jobs', [])
                else:
                    return []
        except FileNotFoundError:
            return []

    def save_delivered_jobs(self):
        """保存已投递记录"""
        today = datetime.now().strftime('%Y-%m-%d')
        data = {
            'date': today,
            'jobs': self.delivered_jobs
        }
        with open('delivered.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def init_browser(self):
        """初始化浏览器"""
        print("正在启动浏览器...")
        chrome_options = Options()

        # 配置浏览器选项
        if self.config['浏览器配置']['无头模式']:
            chrome_options.add_argument('--headless')

        window_size = self.config['浏览器配置']['窗口大小']
        chrome_options.add_argument(f'--window-size={window_size}')

        # 防止被检测
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
        })

        print("浏览器启动成功！")

    def login(self):
        """打开Boss直聘并等待登录"""
        print("正在打开Boss直聘登录页面...")
        self.driver.get('https://www.zhipin.com/')

        # 等待页面加载
        time.sleep(2)

        # 点击登录按钮打开登录窗口
        try:
            login_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.btn-sign-in, .login-btn'))
            )
            login_btn.click()
            print("登录窗口已打开")
        except:
            print("未找到登录按钮，可能已经登录或页面结构变化")

        # 等待二维码加载
        time.sleep(5)

        print("\n" + "="*50)
        print("请在浏览器中扫码登录Boss直聘")
        print("登录成功后程序会自动继续...")
        print("="*50 + "\n")

        # 循环检测登录状态，每30秒提示一次
        max_wait_time = 300  # 最长等待5分钟
        check_interval = 5   # 每5秒检查一次
        remind_interval = 30 # 每30秒提醒一次

        elapsed_time = 0
        last_remind_time = 0

        while elapsed_time < max_wait_time:
            # 检查是否登录成功
            try:
                # 检测登录后才有的元素
                user_element = self.driver.find_elements(By.CSS_SELECTOR, '.user-nav, .nav-user')
                if user_element:
                    print("\n登录成功！")
                    time.sleep(2)
                    return
            except:
                pass

            # 每30秒提醒一次
            if elapsed_time - last_remind_time >= remind_interval:
                print(f"等待登录中...（已等待 {elapsed_time} 秒）")
                last_remind_time = elapsed_time

            time.sleep(check_interval)
            elapsed_time += check_interval

        # 超时
        print("\n登录超时（超过5分钟），请重新运行程序！")
        self.driver.quit()
        exit(1)

    def search_jobs(self):
        """搜索职位"""
        search_config = self.config['搜索配置']
        keyword = search_config['关键词']

        print(f"\n开始搜索职位：{keyword}")

        # 只使用关键词搜索
        search_url = f'https://www.zhipin.com/web/geek/job?query={keyword}'
        self.driver.get(search_url)

        print("等待页面加载...")
        time.sleep(8)  # 一次性等待足够的时间

        print("搜索页面加载完成！")

    def get_job_list(self):
        """获取职位列表"""
        try:
            print("正在查找职位列表...")

            # 等待充足时间让页面加载
            time.sleep(6)

            # 尝试常见的职位列表选择器，使用WebDriverWait等待元素真正出现
            selectors = [
                '.job-card-wrapper',
                '.job-card-box',
                'li.job-card'
            ]

            job_cards = []
            for selector in selectors:
                try:
                    # 等待元素出现，最多等25秒
                    WebDriverWait(self.driver, 25).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # 元素出现后再等3秒确保完全加载
                    time.sleep(3)

                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_cards and len(job_cards) > 0:
                        print(f"找到 {len(job_cards)} 个职位")
                        return job_cards
                except TimeoutException:
                    # 这个选择器超时，尝试下一个
                    continue

            print("未找到职位列表")
            return []

        except Exception as e:
            print(f"获取职位列表出错：{e}")
            return []

    def deliver_resume(self, index):
        """投递简历 - 使用索引而不是元素引用"""
        try:
            # 重新获取职位列表，避免stale element
            selectors = [
                '.job-card-wrapper',
                '.job-card-box',
                'li.job-card'
            ]

            job_cards = []
            for selector in selectors:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if job_cards and len(job_cards) > index:
                    break

            if not job_cards or len(job_cards) <= index:
                print(f"  - 索引{index}超出范围")
                return False

            job_card = job_cards[index]

            # 先获取职位信息和ID（在点击前）
            try:
                job_name = job_card.find_element(By.CSS_SELECTOR, '.job-name, .job-title').text
                company_name = job_card.find_element(By.CSS_SELECTOR, '.company-name, .comp-name').text
            except:
                # 如果找不到，尝试更多选择器
                try:
                    job_name = job_card.find_element(By.CSS_SELECTOR, '[class*="job"]').text
                    company_name = job_card.find_element(By.CSS_SELECTOR, '[class*="company"]').text
                except:
                    job_name = "未知职位"
                    company_name = "未知公司"

            # 获取职位ID
            try:
                job_link = job_card.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                job_id = job_link.split('/')[-1].split('.')[0].split('?')[0] if job_link else str(random.randint(1000000, 9999999))
            except:
                job_id = str(random.randint(1000000, 9999999))

            print(f"\n[{self.today_count + 1}] {company_name} - {job_name}")

            # 检查是否已投递
            if job_id in self.delivered_jobs:
                print("  - 已投递，跳过")
                return False

            # 第1步：点击左侧的职位项
            try:
                print("  - 点击职位...")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job_card)
                time.sleep(1)

                # 点击职位卡片
                try:
                    job_card.click()
                except:
                    self.driver.execute_script("arguments[0].click();", job_card)

                # 等待右侧详情加载
                print("  - 等待详情加载...")
                time.sleep(3)

            except Exception as e:
                print(f"  - 点击职位失败：{e}")
                return False

            # 第2步：在右侧查找"立即沟通"按钮（直接用文本匹配）
            try:
                print("  - 查找立即沟通按钮...")

                chat_btn = None

                # 直接通过文本匹配查找按钮（最可靠的方法）
                all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                all_links = self.driver.find_elements(By.TAG_NAME, 'a')

                for elem in all_buttons + all_links:
                    try:
                        if elem.is_displayed():
                            text = elem.text.strip()
                            # 只匹配"立即沟通"，排除其他文本
                            if text == '立即沟通' or text == '立即聊天' or text == '开始聊天':
                                chat_btn = elem
                                print(f"  - 找到按钮（文本：{text}）")
                                break
                    except:
                        continue

                if not chat_btn:
                    print("  - 未找到立即沟通按钮")
                    return False

                # 检查按钮状态
                try:
                    btn_text = chat_btn.text.strip()

                    # 严格检查：只有"立即沟通"相关文本才继续
                    if btn_text not in ['立即沟通', '立即聊天', '开始聊天', '立即应聘']:
                        if '已沟通' in btn_text or '继续沟通' in btn_text:
                            print(f"  - {btn_text}，跳过")
                            self.delivered_jobs.append(job_id)
                            self.save_delivered_jobs()
                            return False
                        else:
                            print(f"  - 按钮文本不符'{btn_text}'")
                            return False
                except:
                    pass

                # 第3步：点击"立即沟通"
                print(f"  - 点击按钮...")
                try:
                    # 滚动到按钮
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", chat_btn)
                    time.sleep(1)

                    # 点击
                    try:
                        chat_btn.click()
                    except:
                        # 如果直接点击失败，用JavaScript点击
                        self.driver.execute_script("arguments[0].click();", chat_btn)

                except Exception as e:
                    print(f"  - 点击失败：{e}")
                    return False

                time.sleep(3)

                # 第4步：输入并发送招呼语
                print("  - 查找招呼语输入框...")
                try:
                    # 查找输入框（只查找textarea）
                    input_selectors = [
                        'textarea[placeholder*="和BOSS"]',
                        'textarea[placeholder*="打个招呼"]',
                        'textarea.input-area',
                        '.chat-input',
                        'textarea',
                        '.greet-input textarea'
                    ]

                    chat_input = None
                    for selector in input_selectors:
                        try:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for elem in elements:
                                # 检查元素是否可见、可编辑
                                if elem.is_displayed() and elem.is_enabled():
                                    # 确保是textarea或input元素
                                    tag_name = elem.tag_name.lower()
                                    if tag_name in ['textarea', 'input']:
                                        chat_input = elem
                                        print(f"  - 找到输入框：{selector}")
                                        break
                            if chat_input:
                                break
                        except:
                            continue

                    if chat_input:
                        # 输入招呼语
                        greeting = self.config['投递配置']['招呼语']
                        print(f"  - 输入招呼语：{greeting[:20]}...")

                        try:
                            chat_input.clear()
                            time.sleep(0.5)
                        except:
                            pass

                        # 点击输入框激活
                        try:
                            chat_input.click()
                            time.sleep(0.5)
                        except:
                            pass

                        # 输入文本
                        try:
                            chat_input.send_keys(greeting)
                            time.sleep(1.5)
                            print("  - 招呼语已输入")
                        except Exception as e:
                            print(f"  - 输入失败：{e}")
                            # 尝试用JavaScript输入
                            try:
                                self.driver.execute_script(f"arguments[0].value = arguments[1];", chat_input, greeting)
                                print("  - 招呼语已输入（JavaScript）")
                            except:
                                print("  - 输入失败，跳过招呼语")
                                chat_input = None

                        if chat_input:
                            # 查找发送按钮
                            print("  - 查找发送按钮...")
                            send_selectors = [
                                'button.btn-send',
                                '.btn-send',
                                'button[type="submit"]',
                                '.send-btn',
                                'button.primary'
                            ]

                            send_btn = None
                            for selector in send_selectors:
                                try:
                                    send_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    if send_btn and send_btn.is_displayed() and send_btn.is_enabled():
                                        print(f"  - 找到发送按钮：{selector}")
                                        break
                                    else:
                                        send_btn = None
                                except:
                                    continue

                            if send_btn:
                                print("  - 点击发送...")
                                try:
                                    send_btn.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", send_btn)
                                time.sleep(2)
                                print("  - 招呼语已发送")
                            else:
                                print("  - 未找到发送按钮，尝试回车发送...")
                                try:
                                    chat_input.send_keys(Keys.RETURN)
                                    time.sleep(2)
                                    print("  - 招呼语已发送（回车）")
                                except:
                                    print("  - 回车发送失败")
                    else:
                        print("  - 未找到输入框，可能已自动发送")

                except Exception as e:
                    print(f"  - 输入招呼语失败：{e}")
                    print("  - 继续执行...")

                # 第5步：检查是否跳转到聊天页面并返回
                time.sleep(2)
                current_url = self.driver.current_url
                print(f"  - 当前URL：{current_url}")

                if '/chat' in current_url or '/geek/chat' in current_url:
                    print("  - 已跳转到聊天页面，返回职位列表...")
                    self.driver.back()
                    time.sleep(3)
                    print("  - 已返回职位列表")
                else:
                    # 关闭可能的弹窗
                    try:
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(0.5)
                    except:
                        pass

                # 记录已投递
                self.delivered_jobs.append(job_id)
                self.today_count += 1
                self.save_delivered_jobs()

                print(f"  ✓ 投递成功（今日已投 {self.today_count} 个）")
                return True

            except Exception as e:
                print(f"  - 操作失败：{e}")
                return False

        except Exception as e:
            print(f"  - 处理失败：{e}")
            return False

    def random_sleep(self):
        """随机延时"""
        min_sleep = self.config['投递配置']['最小间隔秒数']
        max_sleep = self.config['投递配置']['最大间隔秒数']
        sleep_time = random.uniform(min_sleep, max_sleep)
        time.sleep(sleep_time)

    def run(self):
        """主运行函数"""
        try:
            # 初始化浏览器
            self.init_browser()

            # 登录
            self.login()

            # 搜索职位
            self.search_jobs()

            # 开始投递
            daily_limit = self.config['投递配置']['每日上限']
            print(f"\n开始投递简历（每日上限：{daily_limit}）\n")

            current_index = 0
            failed_count = 0
            max_failed = 5  # 连续失败5次就停止
            job_cards = None  # 缓存职位列表

            while self.today_count < daily_limit:
                # 只在需要时重新获取职位列表
                if job_cards is None or current_index >= len(job_cards):
                    if current_index >= len(job_cards) if job_cards else True:
                        # 需要滚动加载更多
                        if job_cards is not None:
                            print("\n当前页面职位已处理完，向下滚动...")
                            try:
                                self.driver.execute_script("window.scrollBy(0, 800);")
                                time.sleep(5)  # 滚动后等待5秒
                            except:
                                print("无法滚动")

                    # 重新获取职位列表
                    job_cards = self.get_job_list()
                    current_index = 0
                    failed_count = 0

                    if not job_cards:
                        print("未找到职位列表")
                        break

                total_jobs = len(job_cards)
                print(f"\n当前可见职位数：{total_jobs}，正在处理第 {current_index + 1} 个")

                # 处理当前索引的职位
                try:
                    success = self.deliver_resume(current_index)

                    if success:
                        failed_count = 0
                    else:
                        failed_count += 1

                    current_index += 1

                    # 随机延时（增加延时避免刷新太快）
                    if self.today_count < daily_limit and current_index < total_jobs:
                        self.random_sleep()
                        time.sleep(2)  # 额外等待2秒

                except Exception as e:
                    print(f"处理职位时出错：{e}")
                    failed_count += 1
                    current_index += 1

                # 连续失败太多次就停止
                if failed_count >= max_failed:
                    print(f"\n连续失败{max_failed}次，停止投递")
                    break

            print(f"\n\n投递完成！")
            print(f"成功投递：{self.today_count} 个")
            print("\n浏览器将在10秒后关闭...")
            time.sleep(10)

        except KeyboardInterrupt:
            print("\n\n用户中断程序")
        except Exception as e:
            print(f"\n程序出错：{str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()
                print("浏览器已关闭")


if __name__ == '__main__':
    print("=" * 50)
    print("Boss直聘自动投递脚本")
    print("=" * 50)

    bot = BossAutoDeliver()
    bot.run()
