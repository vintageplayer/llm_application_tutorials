import os
import openai
import json
import re
from time import time, sleep
from urllib.parse import urlparse, parse_qs
import textwrap
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

openai.api_key = os.environ["OPENAI_KEY"]

def get_transcript(url):
    url_data = urlparse(url)
    video_id = parse_qs(url_data.query)["v"][0]
    if not video_id:
        print('Video ID not found.')
        return None

    try:
        formatter = TextFormatter()

        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        text = formatter.format_transcript(transcript)
        text = re.sub('\s+', ' ', text).replace('--', '')
        return video_id, text

    except Exception as e:
        print('Error downloading transcript:', e)
        return None

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()


def save_file(content, filepath):
    with open(filepath, 'w', encoding='utf-8') as outfile:
        outfile.write(content)

def wait_for_rate_limit():
	if not hasattr(wait_for_rate_limit, "invocations"):
		wait_for_rate_limit.invocations = []

	MAX_REQUESTS = 3
	MAX_PERIOD = 60
	if len(wait_for_rate_limit.invocations) >= MAX_REQUESTS:
		wait_time = 60 - (time() - wait_for_rate_limit.invocations[0])
		if wait_time <= MAX_PERIOD and wait_time >0:
			print(f'Rate Limit Reached, Sleeping for {wait_time}')
			sleep(wait_time)
		wait_for_rate_limit.invocations = wait_for_rate_limit.invocations[1:]

	wait_for_rate_limit.invocations.append(time())

	return

def gpt3_completion(prompt, model='text-davinci-003', temp=0.5, top_p=1.0, tokens=500, freq_pen=0.25, pres_pen=0.0, stop=['\n']):
	max_retry = 3
	retry = 0
	while True:
		try:
			wait_for_rate_limit()
			response = openai.Completion.create(
				model=model,
				prompt=prompt,
				temperature=temp,
				max_tokens=tokens,
				top_p=top_p,
				frequency_penalty=freq_pen,
				presence_penalty=pres_pen,
				stop=stop)
			text = response['choices'][0]['text'].strip()
			text = re.sub('\s+', ' ', text)
			if not text:
				retry += 1 
				print('No text received. Retrying..')
				print(response)
				continue
			filename = f'gpt3_{time()}.log'
			with open(f'../gpt3_logs/{filename}', 'w') as outfile:
				outfile.write('PROMPT:\n\n' + prompt + '\n\n==========\n\nRESPONSE:\n\n' + text)
			return text

		except Exception as e:
			retry += 1
			if retry >= max_retry:
			    return "GPT3 error: %s" % e
			print('Error communicating with OpenAI:', e)
			sleep(1)

def ask_gpt(text, prompt_file, output_file, job='SUMMARY'):
    # Summarize chunks
    chunks = textwrap.wrap(text, width=10000)
    results = list()
    for i, chunk in enumerate(chunks):
        prompt = open_file(prompt_file).replace('<<CONTENT>>', chunk)
        prompt = prompt.encode(encoding='ASCII',errors='ignore').decode()
        output = ''
        if job=='SUMMARY':
            output = gpt3_completion(prompt, tokens=500)
        elif job == 'REWRITE':
            output = gpt3_completion(prompt, tokens=2048)
        results.append(output)
        print(f'{i+1} of {len(chunks)}\n{output}\n\n\n')

    return results

url = 'https://www.youtube.com/watch?v=kiMTRQXBol0&ab_channel=All-InPodcast'

# Download transcript
video_id, text = get_transcript(url)

# Summarize the transcript (chunk by chunk if needed)
if text:
    # Summarize transcript
    output_file = f'summary_{video_id}_{time()}.txt'

    results = ask_gpt(text, 'prompt_summary.txt', 'SUMMARY')
    summary = '\n\n'.join(results)
    save_file(summary, output_file)

    # # Summarize the summary
    if len(results) > 1:
        new_summary = ask_gpt(summary, 'prompt_rewrite.txt', 'REWRITE')
        save_file('\n\n'.join(new_summary), output_file.replace('.txt', '_2.txt'))

    print('----- Mission Complete -----')
