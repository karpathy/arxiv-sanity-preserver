import os
import pdb


def is_int(str):
  try:
    int(str)
    return True
  except ValueError:
    return False

def not_char(ch):
  if ((ch>='a') and (ch<='z')) or ((ch>='A') and (ch<='Z')):
    return False
  else:
    return True

os.system('mkdir -p bib')

filelist = os.listdir('txt')

for f in filelist:
  if not f.endswith('.txt'):
    continue
  else:
    print f

  inputfilename = os.path.join('txt', f)

  outputfilename = os.path.join('bib', f)
  outputfilename = outputfilename[0:-4] + '.bib.txt'

  with open(inputfilename, 'r') as inputfile:
    with open(outputfilename, 'w') as outputfile:
      # number of bib entries parsed
      bib_count = 0

      # number of lines that has been processed for the current bib
      current_line_count = 0

      # maximum number of lines a single bib entry can have
      max_line_count = 5

      bib_entry_string = ""
      bib_entry_ended = False

      start_parsing = False

      for line in inputfile:
        if ("References" in line) or ("REFERENCES" in line):
          start_parsing = True
          current_line_count = 0
          bib_entry_string = ""
          bib_entry_ended = False
          continue

        if start_parsing:
          # pdb.set_trace()
          # the last entry of curret_line is \n
          bib_entry_string += line[0:-1]

          # current line ends with a period
          if line[-2] == '.':
            if is_int(line[-3]) and is_int(line[-4]):
              bib_entry_ended = True

          if bib_entry_ended:
            bib_entry_string += '\n'

            pos = 0
            while not_char(bib_entry_string[pos]):
              pos += 1
            outputfile.write(bib_entry_string[pos::])
            bib_count += 1

            bib_entry_string = ""
            bib_entry_ended = False
            current_line_count = 0
          else:
            current_line_count += 1

          # end of current bib section
          if current_line_count > max_line_count:
            start_parsing = False

        # found some bib entries in the previous section
        if (not start_parsing) and (bib_count > 0):
          break

      inputfile.close()
      outputfile.close()
