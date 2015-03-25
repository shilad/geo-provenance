from gputils import *

from gpinfer import LogisticInferrer

def evaluate(gold):
    folds = 7
    subsets = list([[] for i in range(folds)])
    for (i, d) in enumerate(gold):
        subsets[i % folds].append(d)

    correct = 0
    total = 0
    missed_ps = []
    correct_ps = []
    for i in range(folds):
        test = subsets[i]
        train = sum(subsets[0:i] + subsets[i+1:], [])
        inf = LogisticInferrer()
        inf.train(train)
        for (url, actual) in test:
            total += 1
            (conf, dist) = inf.infer(url)
            if not dist:
                warn('no prediction for %s' % url)
                continue
            maxp = max(dist.values())
            bestc = [c for c in dist if dist[c] == maxp][0]
            if bestc == actual:
                correct_ps.append(maxp)
                correct += 1
            else:
                missed_ps.append(maxp)
                print 'missed', url, '- guessed', bestc, 'was', actual

    inf = LogisticInferrer()
    inf.train(gold)

    print '\n\nmodel results:'
    print '%d of %d correct (%.2f%%)' % (correct, total, 100.0 * correct / total)
    print 'calibration: correct mean probability is: %.3f' % (sum(correct_ps) / len(correct_ps))
    print 'calibration: incorrect mean probability is: %.3f' % (sum(missed_ps) / len(missed_ps))
    print 'final model:', inf.get_equation()

if __name__ == '__main__':
    gold = read_gold()
    evaluate(gold)