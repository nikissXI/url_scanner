from httpx import AsyncClient
from asyncio import run, gather, sleep
import pandas as pd
from re import findall
from socket import gethostbyname
from json import loads

timeout = 3 # 超时
together = 10 # 并发数
input_file = "urls.txt" # 输入文件名
output_file = "result.csv" # 输出文件名


fr = open(input_file, mode="r+", encoding="utf8")
domain_lines = fr.readlines()
fr.close()
success_list = []
fail_list = []
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.124 Safari/537.36 Edg/102.0.1245.41"


async def send_req(url):
    url_params = url.split("://")
    host = url_params[1].split("/")[0]
    async with AsyncClient(verify=False) as c:
        res = await c.get(
            url,
            headers={"User-Agent": user_agent},
            timeout=timeout,
        )

    # 获取title
    title = findall("<title>(.+)</title>", res.text)
    if title:
        title = title[0]
    else:
        title = ""
    # proxies = {"http://": "http://127.0.0.1:7890", "https://": "http://127.0.0.1:7890"}
    # 查询IP和归属地
    ip = gethostbyname(host)
    async with AsyncClient(verify=False) as c:
        ip_info = await c.get(
            f"https://ip.useragentinfo.com/json?ip={ip}",
            headers={"User-Agent": user_agent},
            timeout=timeout,
        )

    ip_info = loads(ip_info.text)
    addr = (
        f"{ip_info['country']}{ip_info['province']}{ip_info['city']}{ip_info['area']}"
    )
    isp = f"{ip_info['isp']}"
    # 检查是否有跳转
    if 300 <= res.status_code <= 399:
        location = res.headers["location"]
        # 路径，非url
        if location.find("http") == -1:
            url_params = url.split("://")
            location = f"{url_params[0]}://{host}" + location
        else:
            title = location
    else:
        location = ""
    return (res.status_code, title, location, ip, addr, isp)


async def test_url(host):
    # 域名
    if host.find("http") == -1:
        https_url = f"https://{host}/"
        http_url = f"http://{host}/"
        try:
            print(https_url)
            status_code, title, location, ip, addr, isp = await send_req(https_url)
            success_list.append((host, https_url, status_code, title, ip, addr, isp))
            if location:
                await test_url(location)
        except Exception as e:
            fail_list.append((host, https_url, "访问失败", repr(e)))

            try:
                print(http_url)
                status_code, title, location, ip, addr, isp = await send_req(http_url)
                success_list.append((host, http_url, status_code, title, ip, addr, isp))
                if location:
                    await test_url(location)
            except Exception as e:
                fail_list.append((host, http_url, "访问失败", repr(e)))

    # url
    else:
        url = host
        print(url)
        url_params = url.split("://")
        host = url_params[1].split("/")[0]
        try:
            status_code, title, location, ip, addr, isp = await send_req(url)
            success_list.append((host, url, status_code, title, ip, addr, isp))
            if location:
                await test_url(location)
        except Exception as e:
            fail_list.append((host, url, "访问失败", repr(e)))


async def main():
    global together
    first_run = True
    last_fail_count = 0
    run_times = 0

    while True:
        # 首次运行
        if first_run:
            count = len(domain_lines)
            done = 0
            testc = 0
        # 否则
        else:
            url_list = []
            for a, b, c, d in fail_list:
                url_list.append(b)
            fail_list.clear()
            count = len(url_list)
            done = 0
            testc = 0

        while done < count:
            if done + together > count:
                done_end = count
            else:
                done_end = done + together
            task = [
                test_url(host.replace("\n", "")) for host in domain_lines[done:done_end]
            ]
            testc += len(domain_lines[done:done_end])
            done += together
            await gather(*task)
            await sleep(3)

        first_run = False
        if together > 1:
            together = int(together / 2)
        run_times += 1
        print(f"第{run_times}轮完成")
        # 检查是否跳出
        if last_fail_count == len(fail_list):
            break
        else:
            last_fail_count = len(fail_list)

    # 输出表格
    no_same = []
    host_list = []
    url_list = []
    status_code_list = []
    title_list = []
    ip_list = []
    addr_list = []
    isp_list = []

    for a, b, c, d, e, f, g in success_list:
        if b not in no_same:
            host_list.append(a)
            url_list.append(b)
            status_code_list.append(c)
            title_list.append(d)
            ip_list.append(e)
            addr_list.append(f)
            isp_list.append(g)
            no_same.append(b)

    for a, b, c, d in fail_list:
        if b not in no_same:
            host_list.append(a)
            url_list.append(b)
            status_code_list.append(c)
            title_list.append(d)
            ip_list.append("")
            addr_list.append("")
            isp_list.append("")
            no_same.append(b)

    dict = {
        "ip": ip_list,
        "url": url_list,
        "title": title_list,
        "host": host_list,
        "code": status_code_list,
        "addr": addr_list,
        "isp": isp_list,
    }
    df = pd.DataFrame(dict)
    df.to_csv(output_file, encoding="utf_8_sig")

    print(f"共运行{run_times}轮\n访问成功url数量{len(success_list)}\n访问失败url数量{len(fail_list)}")


if __name__ == "__main__":
    run(main())
